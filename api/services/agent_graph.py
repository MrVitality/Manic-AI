"""Stateful Agent Graph -- Generator-Critic loop with Redis state persistence.

Implements a multi-step reasoning pipeline:
    plan -> retrieve -> generate (with ReAct tool loop) -> critique -> (revise | complete)

State is persisted in Redis so each step can be resumed independently.
"""

import json
import logging
import re
import time
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, List, Optional
from uuid import uuid4

import httpx

from api.config import settings
from api.services.embedding import generate_embedding
from api.services.model_router import chat_completion

logger = logging.getLogger(__name__)

MAX_REVISION_CYCLES = 3
CRITIQUE_PASS_THRESHOLD = 7
MAX_TOOL_CALLS_PER_GENERATION = 5

# Matches: <tool_call name="tool_name">{"arg": "value"}</tool_call>
_TOOL_CALL_RE = re.compile(
    r'<tool_call\s+name=["\'](?P<name>[^"\']+)["\']>'
    r'(?P<args>.*?)'
    r'</tool_call>',
    re.DOTALL,
)


# ---------------------------------------------------------------------------
# Redis state helpers
# ---------------------------------------------------------------------------

async def _get_redis():
    """Obtain the module-level Redis client from the embedding service."""
    from api.services.embedding import _redis
    return _redis


async def _save_state(run_id: str, state: Dict[str, Any]) -> None:
    """Persist agent run state to Redis."""
    redis = await _get_redis()
    if redis:
        try:
            await redis.setex(
                f"agent:run:{run_id}",
                settings.AGENT_STATE_TTL_SECONDS,
                json.dumps(state, default=str),
            )
        except Exception:
            logger.warning("Failed to persist agent state for %s", run_id)


async def _load_state(run_id: str) -> Optional[Dict[str, Any]]:
    """Load agent run state from Redis."""
    redis = await _get_redis()
    if redis:
        try:
            raw = await redis.get(f"agent:run:{run_id}")
            if raw:
                return json.loads(raw)
        except Exception:
            logger.warning("Failed to load agent state for %s", run_id)
    return None


# ---------------------------------------------------------------------------
# Agent steps
# ---------------------------------------------------------------------------

async def _plan(
    query: str,
    http_client: httpx.AsyncClient,
    model: str,
) -> List[str]:
    """Break a query into sub-steps for retrieval and reasoning."""
    messages = [
        {
            "role": "system",
            "content": (
                "You are a planning agent. Break the user's question into 2-5 concrete "
                "sub-questions or retrieval queries. Return ONLY a JSON array of strings, "
                "nothing else. Example: [\"sub-query 1\", \"sub-query 2\"]"
            ),
        },
        {"role": "user", "content": query},
    ]

    result = await chat_completion(messages, model, stream=False, http_client=http_client, temperature=0.3)
    text = result["content"].strip()

    # Parse JSON array from the response
    try:
        # Handle cases where the model wraps in markdown code blocks
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()
        steps = json.loads(text)
        if isinstance(steps, list) and all(isinstance(s, str) for s in steps):
            return steps
    except (json.JSONDecodeError, IndexError):
        pass

    # Fallback: use the original query as a single step
    logger.warning("Plan parsing failed, falling back to single-step for run")
    return [query]


async def _retrieve(
    sub_query: str,
    http_client: httpx.AsyncClient,
    db_pool: Optional[Any],
) -> List[Dict[str, Any]]:
    """Search the knowledge base for relevant context."""
    if not db_pool:
        return []

    try:
        query_embedding = await generate_embedding(sub_query, client=http_client)
        from api.repositories.supabase_vector import SupabaseVectorRepository

        repo = SupabaseVectorRepository(db_pool)
        results = await repo.hybrid_search(
            sub_query,
            query_embedding,
            top_k=settings.RAG_TOP_K,
            keyword_weight=settings.RAG_KEYWORD_WEIGHT,
        )
        return results
    except Exception:
        logger.warning("Retrieval failed for sub-query: %s", sub_query[:100])
        return []


def _build_tool_description_string() -> str:
    """Build a human-readable tool catalogue from the plugin registry."""
    from api.plugins import list_tools
    tools = list_tools()
    if not tools:
        return ""
    lines = ["You have access to these tools:"]
    for t in tools:
        lines.append(f"  - {t['name']}: {t['description']}")
    lines.append(
        '\nTo use a tool, write exactly: '
        '<tool_call name="tool_name">{"arg": "value"}</tool_call>\n'
        "Wait for the tool result before continuing your response."
    )
    return "\n".join(lines)


async def _execute_tool_call(name: str, args_json: str) -> str:
    """Look up and call a plugin tool, returning a string result."""
    from api.plugins import get_tool
    func = get_tool(name)
    if func is None:
        return f"[tool_error: unknown tool '{name}']"

    try:
        args = json.loads(args_json) if args_json.strip() else {}
    except json.JSONDecodeError as exc:
        return f"[tool_error: invalid JSON arguments for '{name}': {exc}]"

    try:
        if not isinstance(args, dict):
            return f"[tool_error: arguments for '{name}' must be a JSON object, got {type(args).__name__}]"
        result = await func(**args)
        return json.dumps(result, default=str)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Tool '%s' raised an exception: %s", name, exc)
        return f"[tool_error: '{name}' failed: {exc}]"


async def _generate(
    query: str,
    context: List[Dict[str, Any]],
    http_client: httpx.AsyncClient,
    model: str,
    *,
    previous_answer: Optional[str] = None,
    critique_feedback: Optional[str] = None,
    tool_steps: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """Generate an answer using retrieved context, with a ReAct tool-calling loop.

    The loop allows the model to call up to MAX_TOOL_CALLS_PER_GENERATION
    registered plugin tools before producing its final answer.  Each tool
    result is injected back into the conversation as an assistant/user
    message pair so the model can reason over it.

    Args:
        tool_steps: Optional list to which tool-call audit entries are appended.
                    Each entry contains ``tool``, ``args_json``, and ``result``.
    """
    if tool_steps is None:
        tool_steps = []

    context_text = ""
    if context:
        context_text = "\n\n---\n\n".join(
            f"[Source {i+1}]: {c.get('content', '')}" for i, c in enumerate(context)
        )

    tool_desc = _build_tool_description_string()

    system_parts = [
        "You are a knowledgeable assistant. Answer the question using the provided context. "
        "If the context is insufficient, say so and use your general knowledge.",
    ]
    if tool_desc:
        system_parts.append(tool_desc)
    if previous_answer and critique_feedback:
        system_parts.append(
            f"\n\nYour previous answer was:\n{previous_answer}\n\n"
            f"It received this feedback:\n{critique_feedback}\n\n"
            "Please revise your answer to address the feedback."
        )

    user_content = query
    if context_text:
        user_content = f"Context:\n{context_text}\n\nQuestion: {query}\n\nAnswer:"

    messages: List[Dict[str, str]] = [
        {"role": "system", "content": "\n\n".join(system_parts)},
        {"role": "user", "content": user_content},
    ]

    # ReAct loop: let the model call tools, then continue generating
    for call_index in range(MAX_TOOL_CALLS_PER_GENERATION):
        result = await chat_completion(
            messages, model, stream=False, http_client=http_client, temperature=0.5
        )
        response_text: str = result["content"]

        match = _TOOL_CALL_RE.search(response_text)
        if not match:
            # No tool call in this response — we have the final answer
            return response_text

        tool_name = match.group("name")
        args_json = match.group("args").strip()

        logger.info(
            "ReAct tool call %d/%d: tool=%s args=%s",
            call_index + 1,
            MAX_TOOL_CALLS_PER_GENERATION,
            tool_name,
            args_json[:200],
        )

        tool_result = await _execute_tool_call(tool_name, args_json)

        # Record the tool call for the caller to log in state steps
        tool_steps.append({
            "tool": tool_name,
            "args_json": args_json,
            "result": tool_result[:500],
        })

        # Extend conversation: assistant's tool-call turn + injected tool result
        messages.append({"role": "assistant", "content": response_text})
        messages.append({
            "role": "user",
            "content": (
                f"Tool result for <tool_call name=\"{tool_name}\">:\n{tool_result}\n\n"
                "Continue your answer using the tool result above."
            ),
        })

    # Fell through the loop — do one final generation without tool calls
    logger.warning(
        "ReAct loop reached max tool calls (%d); generating final answer",
        MAX_TOOL_CALLS_PER_GENERATION,
    )
    final = await chat_completion(
        messages, model, stream=False, http_client=http_client, temperature=0.5
    )
    return final["content"]


async def _critique(
    answer: str,
    query: str,
    http_client: httpx.AsyncClient,
    model: str,
) -> Dict[str, Any]:
    """Score the answer quality (0-10) and identify gaps."""
    messages = [
        {
            "role": "system",
            "content": (
                "You are a critical reviewer. Evaluate the answer for the given question. "
                "Return ONLY valid JSON with these fields:\n"
                '- "score": integer 0-10 (10 = perfect)\n'
                '- "gaps": list of strings describing what is missing or wrong\n'
                '- "feedback": a brief paragraph of constructive feedback\n'
                "Example: {\"score\": 7, \"gaps\": [\"missing source citations\"], \"feedback\": \"Good but needs sources.\"}"
            ),
        },
        {
            "role": "user",
            "content": f"Question: {query}\n\nAnswer: {answer}",
        },
    ]

    result = await chat_completion(messages, model, stream=False, http_client=http_client, temperature=0.2)
    text = result["content"].strip()

    try:
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()
        critique = json.loads(text)
        return {
            "score": int(critique.get("score", 5)),
            "gaps": critique.get("gaps", []),
            "feedback": critique.get("feedback", ""),
        }
    except (json.JSONDecodeError, ValueError):
        logger.warning("Critique parsing failed, defaulting to pass")
        return {"score": 8, "gaps": [], "feedback": "Unable to parse critique; accepting answer."}


# ---------------------------------------------------------------------------
# Main agent orchestrator
# ---------------------------------------------------------------------------

async def run_agent(
    query: str,
    http_client: httpx.AsyncClient,
    db_pool: Optional[Any],
    *,
    model: Optional[str] = None,
    run_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute the full Generator-Critic agent loop.

    Returns a structured result with the final answer and all steps taken.
    """
    run_id = run_id or str(uuid4())
    model = model or settings.CHAT_MODEL
    started_at = time.time()

    steps: List[Dict[str, Any]] = []
    state = {
        "run_id": run_id,
        "query": query,
        "model": model,
        "status": "running",
        "steps": steps,
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    await _save_state(run_id, state)

    # Step 1: Plan
    steps.append({"step": "plan", "status": "running", "timestamp": _now()})
    await _save_state(run_id, state)

    sub_queries = await _plan(query, http_client, model)
    steps[-1].update({"status": "completed", "result": sub_queries})
    await _save_state(run_id, state)

    # Step 2: Retrieve for each sub-query
    steps.append({"step": "retrieve", "status": "running", "timestamp": _now()})
    await _save_state(run_id, state)

    all_context: List[Dict[str, Any]] = []
    seen_ids = set()
    for sq in sub_queries:
        results = await _retrieve(sq, http_client, db_pool)
        for r in results:
            rid = r.get("id", id(r))
            if rid not in seen_ids:
                seen_ids.add(rid)
                all_context.append(r)

    steps[-1].update({
        "status": "completed",
        "result": f"{len(all_context)} unique chunks retrieved from {len(sub_queries)} sub-queries",
    })
    await _save_state(run_id, state)

    # Step 3-5: Generate -> Critique -> Revise loop
    answer = ""
    final_critique = None

    for cycle in range(MAX_REVISION_CYCLES):
        # Generate
        step_name = "generate" if cycle == 0 else f"revise_{cycle}"
        steps.append({"step": step_name, "status": "running", "timestamp": _now()})
        await _save_state(run_id, state)

        previous_answer = answer if cycle > 0 else None
        critique_feedback = final_critique["feedback"] if final_critique else None

        tool_steps: List[Dict[str, Any]] = []
        answer = await _generate(
            query,
            all_context,
            http_client,
            model,
            previous_answer=previous_answer,
            critique_feedback=critique_feedback,
            tool_steps=tool_steps,
        )

        # Mark the generate/revise step complete first, then append tool-call steps
        steps[-1].update({"status": "completed", "result": answer[:500]})

        # Log each tool call that occurred during this generation as its own step
        for ts in tool_steps:
            steps.append({
                "step": f"tool_call:{ts['tool']}",
                "status": "completed",
                "timestamp": _now(),
                "tool": ts["tool"],
                "args_json": ts["args_json"],
                "result_preview": ts["result"],
            })

        await _save_state(run_id, state)

        # Critique
        steps.append({"step": f"critique_{cycle + 1}", "status": "running", "timestamp": _now()})
        await _save_state(run_id, state)

        final_critique = await _critique(answer, query, http_client, model)
        steps[-1].update({"status": "completed", "result": final_critique})
        await _save_state(run_id, state)

        if final_critique["score"] >= CRITIQUE_PASS_THRESHOLD:
            break

    elapsed_ms = round((time.time() - started_at) * 1000, 1)

    state.update({
        "status": "completed",
        "answer": answer,
        "critique": final_critique,
        "sources_count": len(all_context),
        "elapsed_ms": elapsed_ms,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    })
    await _save_state(run_id, state)

    return {
        "run_id": run_id,
        "query": query,
        "answer": answer,
        "critique": final_critique,
        "steps": steps,
        "sources_count": len(all_context),
        "model": model,
        "elapsed_ms": elapsed_ms,
        "status": "completed",
    }


async def get_run_status(run_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve the current status of an agent run from Redis."""
    return await _load_state(run_id)


async def stream_agent_steps(
    query: str,
    http_client: httpx.AsyncClient,
    db_pool: Optional[Any],
    *,
    model: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    """Execute the agent loop and yield SSE events for each step.

    Each event is a JSON-encoded dict with step info.
    """
    run_id = str(uuid4())
    model = model or settings.CHAT_MODEL

    yield f"data: {json.dumps({'type': 'start', 'run_id': run_id})}\n\n"

    # Plan
    yield f"data: {json.dumps({'type': 'step', 'step': 'plan', 'status': 'running'})}\n\n"
    sub_queries = await _plan(query, http_client, model)
    yield f"data: {json.dumps({'type': 'step', 'step': 'plan', 'status': 'completed', 'result': sub_queries})}\n\n"

    # Retrieve
    yield f"data: {json.dumps({'type': 'step', 'step': 'retrieve', 'status': 'running'})}\n\n"
    all_context: List[Dict[str, Any]] = []
    seen_ids = set()
    for sq in sub_queries:
        results = await _retrieve(sq, http_client, db_pool)
        for r in results:
            rid = r.get("id", id(r))
            if rid not in seen_ids:
                seen_ids.add(rid)
                all_context.append(r)
    yield f"data: {json.dumps({'type': 'step', 'step': 'retrieve', 'status': 'completed', 'chunks': len(all_context)})}\n\n"

    # Generate-Critique loop
    answer = ""
    final_critique = None

    for cycle in range(MAX_REVISION_CYCLES):
        step_name = "generate" if cycle == 0 else f"revise_{cycle}"
        yield f"data: {json.dumps({'type': 'step', 'step': step_name, 'status': 'running'})}\n\n"

        tool_steps: List[Dict[str, Any]] = []
        answer = await _generate(
            query,
            all_context,
            http_client,
            model,
            previous_answer=answer if cycle > 0 else None,
            critique_feedback=final_critique["feedback"] if final_critique else None,
            tool_steps=tool_steps,
        )

        # Emit an SSE event for each tool call that happened during generation
        for ts in tool_steps:
            yield f"data: {json.dumps({'type': 'tool_call', 'tool': ts['tool'], 'args_json': ts['args_json'], 'result_preview': ts['result']})}\n\n"

        yield f"data: {json.dumps({'type': 'step', 'step': step_name, 'status': 'completed', 'preview': answer[:300]})}\n\n"

        yield f"data: {json.dumps({'type': 'step', 'step': f'critique_{cycle + 1}', 'status': 'running'})}\n\n"
        final_critique = await _critique(answer, query, http_client, model)
        yield f"data: {json.dumps({'type': 'step', 'step': f'critique_{cycle + 1}', 'status': 'completed', 'score': final_critique['score']})}\n\n"

        if final_critique["score"] >= CRITIQUE_PASS_THRESHOLD:
            break

    # Final result
    yield f"data: {json.dumps({'type': 'result', 'run_id': run_id, 'answer': answer, 'critique': final_critique, 'sources_count': len(all_context)})}\n\n"
    yield f"data: {json.dumps({'type': 'done'})}\n\n"

    # Persist final state
    state = {
        "run_id": run_id,
        "query": query,
        "answer": answer,
        "model": model,
        "status": "completed",
        "critique": final_critique,
        "sources_count": len(all_context),
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }
    await _save_state(run_id, state)


def _now() -> str:
    """ISO-formatted UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()
