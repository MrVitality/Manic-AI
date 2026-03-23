"""Multi-Model Consensus endpoint.

POST /v1/chat/consensus

Runs the same chat prompt against multiple models in parallel, then feeds all
responses to a meta-critic LLM that identifies agreement/disagreement and
synthesises a single authoritative answer.

Response shape
--------------
{
    "consensus": "...",
    "individual_responses": [
        {"model": "llama3.2:3b", "content": "..."},
        ...
    ],
    "agreement_score": 0.85   # float 0.0–1.0
}
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from api.config import settings
from api.dependencies import get_http_client
from api.middleware.rate_limit import limiter
from api.schemas.chat import ChatMessage
from api.schemas.envelope import ok
from api.services.model_router import chat_completion

logger = logging.getLogger(__name__)

router = APIRouter()

# Default models to use when the caller supplies none.
_DEFAULT_MODELS = ["llama3.2:3b", "mistral:7b", "gemma2:9b"]

# Maximum number of models the caller can specify in a single request.
_MAX_MODELS = 10


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class ConsensusRequest(BaseModel):
    """Body for POST /v1/chat/consensus."""

    messages: List[ChatMessage] = Field(
        ...,
        max_length=200,
        description="Conversation history — same format as /v1/chat.",
    )
    models: Optional[List[str]] = Field(
        None,
        max_length=_MAX_MODELS,
        description=(
            f"Models to query. Defaults to up to {len(_DEFAULT_MODELS)} "
            "pre-configured models when omitted."
        ),
    )
    temperature: Optional[float] = Field(0.7, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(2048, ge=1, le=32_768)


class IndividualResponse(BaseModel):
    model: str
    content: str
    error: Optional[str] = None


class ConsensusResponse(BaseModel):
    consensus: str
    individual_responses: List[IndividualResponse]
    agreement_score: float


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _query_model(
    model: str,
    messages: List[Dict[str, str]],
    http_client: httpx.AsyncClient,
    temperature: float,
    max_tokens: int,
) -> IndividualResponse:
    """Query a single model and return a normalised response object."""
    try:
        result = await chat_completion(
            messages,
            model,
            stream=False,
            http_client=http_client,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return IndividualResponse(model=model, content=result["content"])
    except Exception as exc:
        logger.warning("consensus: model %s failed — %s", model, exc)
        return IndividualResponse(model=model, content="", error=str(exc))


def _build_meta_critic_prompt(
    question: str,
    responses: List[IndividualResponse],
) -> List[Dict[str, str]]:
    """Build the meta-critic messages list."""
    blocks = []
    for i, resp in enumerate(responses, start=1):
        if resp.error:
            blocks.append(f"Model {i} ({resp.model}): [ERROR — {resp.error}]")
        else:
            blocks.append(f"Model {i} ({resp.model}):\n{resp.content}")

    answers_text = "\n\n---\n\n".join(blocks)

    system = (
        "You are a meta-critic synthesiser. You will receive the same question answered "
        "by multiple AI models. Your task is:\n"
        "1. Identify where the models AGREE (common facts, conclusions, recommendations).\n"
        "2. Identify where they DISAGREE or contradict each other.\n"
        "3. Produce a single synthesised answer that incorporates the strongest points "
        "from all models, notes any unresolved disagreements, and gives the user the "
        "most accurate, complete response possible.\n"
        "4. Estimate an agreement_score between 0.0 (total disagreement) and 1.0 "
        "(perfect agreement) across the model answers.\n\n"
        "Return ONLY valid JSON with this structure:\n"
        '{"consensus": "<synthesised answer>", "agreement_score": <float 0.0-1.0>, '
        '"agreements": ["<point>", ...], "disagreements": ["<point>", ...]}\n\n'
        "Do not wrap the JSON in markdown code fences."
    )

    user = (
        f"Original question:\n{question}\n\n"
        f"Model answers:\n\n{answers_text}"
    )

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def _extract_last_user_question(messages: List[ChatMessage]) -> str:
    """Pull the last user message as the question for the meta-critic."""
    for msg in reversed(messages):
        if msg.role == "user":
            return msg.content
    return "User question not found."


def _parse_meta_critic_response(raw: str) -> Dict[str, Any]:
    """Parse the meta-critic JSON, with a safe fallback on parse failure."""
    text = raw.strip()
    if text.startswith("```"):
        # Strip markdown code fences if the model includes them despite instructions.
        parts = text.split("```")
        if len(parts) >= 2:
            text = parts[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()
    try:
        parsed = json.loads(text)
        return {
            "consensus": str(parsed.get("consensus", raw)),
            "agreement_score": float(
                max(0.0, min(1.0, parsed.get("agreement_score", 0.5)))
            ),
        }
    except (json.JSONDecodeError, ValueError, TypeError):
        logger.warning("consensus: failed to parse meta-critic JSON, using raw text")
        return {"consensus": raw, "agreement_score": 0.5}


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.post("/chat/consensus", response_model=None, tags=["chat"])
@limiter.limit(f"{settings.RATE_LIMIT_PER_MINUTE}/minute")
async def chat_consensus(
    request: Request,
    body: ConsensusRequest,
    client: httpx.AsyncClient = Depends(get_http_client),
):
    """Run a chat prompt against multiple models and synthesise a consensus answer.

    - Queries all specified models in parallel.
    - Feeds results to a meta-critic LLM for synthesis and agreement scoring.
    - Returns individual responses alongside the synthesised consensus.
    """
    models: List[str] = body.models or _DEFAULT_MODELS

    if not models:
        raise HTTPException(status_code=422, detail="At least one model must be specified")

    # Convert Pydantic messages to plain dicts for model_router.
    messages_dicts = [{"role": m.role, "content": m.content} for m in body.messages]
    temperature = body.temperature or 0.7
    max_tokens = body.max_tokens or 2048

    # Step 1: Query all models in parallel.
    tasks = [
        _query_model(model, messages_dicts, client, temperature, max_tokens)
        for model in models
    ]
    individual: List[IndividualResponse] = list(
        await asyncio.gather(*tasks, return_exceptions=False)
    )

    # Determine which responses actually succeeded.
    successful = [r for r in individual if not r.error and r.content]
    if not successful:
        raise HTTPException(
            status_code=502,
            detail="All model queries failed — no responses to synthesise",
        )

    # Step 2: Build and run the meta-critic prompt using the primary chat model.
    question = _extract_last_user_question(body.messages)
    meta_messages = _build_meta_critic_prompt(question, individual)

    try:
        meta_result = await chat_completion(
            meta_messages,
            settings.CHAT_MODEL,
            stream=False,
            http_client=client,
            temperature=0.2,  # low temperature for consistent synthesis
            max_tokens=max_tokens,
        )
        parsed = _parse_meta_critic_response(meta_result["content"])
    except Exception:
        logger.exception("consensus: meta-critic call failed")
        # Degrade gracefully: concatenate successful answers as the consensus.
        combined = "\n\n---\n\n".join(
            f"[{r.model}]: {r.content}" for r in successful
        )
        parsed = {"consensus": combined, "agreement_score": 0.5}

    response = ConsensusResponse(
        consensus=parsed["consensus"],
        individual_responses=individual,
        agreement_score=parsed["agreement_score"],
    )

    return ok(
        response.model_dump(),
        meta={
            "models_queried": len(models),
            "models_succeeded": len(successful),
            "models_failed": len(individual) - len(successful),
        },
    )
