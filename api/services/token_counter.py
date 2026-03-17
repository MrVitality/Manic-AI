"""Token counting and context window budget management.

Uses a chars/4 heuristic for token estimation. If tiktoken is available,
it will be used for more accurate counts.
"""

import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Default context window size (configurable via settings)
DEFAULT_CONTEXT_WINDOW = 4096

# Budget allocation ratios
SYSTEM_PROMPT_BUDGET = 500  # fixed token reserve for system prompt
RAG_CONTEXT_RATIO = 0.40    # 40% of remaining budget for RAG context
HISTORY_RATIO = 0.60        # 60% of remaining budget for conversation history

# Try to use tiktoken for accurate counting; fall back to heuristic
_tiktoken_encoding = None
try:
    import tiktoken
    _tiktoken_encoding = tiktoken.get_encoding("cl100k_base")
    logger.info("tiktoken available -- using cl100k_base for token counting")
except ImportError:
    logger.info("tiktoken not installed -- using chars/4 heuristic for token counting")


def estimate_tokens(text: str) -> int:
    """Estimate the number of tokens in a text string.

    Uses tiktoken cl100k_base if available, otherwise falls back to
    a chars/4 heuristic that slightly overestimates (safer for budgeting).
    """
    if not text:
        return 0
    if _tiktoken_encoding is not None:
        return len(_tiktoken_encoding.encode(text))
    return max(1, len(text) // 4)


def estimate_messages_tokens(messages: List[Dict[str, str]]) -> int:
    """Estimate total tokens across a list of chat messages.

    Each message has a small overhead (~4 tokens) for role/formatting.
    """
    total = 0
    for msg in messages:
        total += 4  # role + formatting overhead per message
        total += estimate_tokens(msg.get("content", ""))
    return total


def compute_budgets(
    context_window: int = DEFAULT_CONTEXT_WINDOW,
    system_prompt_tokens: Optional[int] = None,
) -> Dict[str, int]:
    """Compute token budgets for RAG context and conversation history.

    Returns a dict with keys: system_prompt, rag_context, history, total.
    """
    sys_budget = system_prompt_tokens if system_prompt_tokens is not None else SYSTEM_PROMPT_BUDGET
    remaining = max(0, context_window - sys_budget)
    rag_budget = int(remaining * RAG_CONTEXT_RATIO)
    history_budget = remaining - rag_budget  # give history the remainder to avoid rounding loss

    return {
        "system_prompt": sys_budget,
        "rag_context": rag_budget,
        "history": history_budget,
        "total": context_window,
    }


def truncate_messages_to_budget(
    messages: List[Dict[str, str]],
    token_budget: int,
) -> List[Dict[str, str]]:
    """Truncate conversation history to fit within token budget.

    Keeps the system message (if any) and the most recent user message,
    then fills backward from newest to oldest until the budget is exhausted.
    Oldest non-essential messages are dropped first.
    """
    if not messages:
        return []

    # Separate system messages and conversation messages
    system_msgs = [m for m in messages if m.get("role") == "system"]
    conv_msgs = [m for m in messages if m.get("role") != "system"]

    # Always keep system messages; count their cost
    system_cost = estimate_messages_tokens(system_msgs)
    remaining_budget = max(0, token_budget - system_cost)

    if not conv_msgs:
        return system_msgs

    # Always keep the last message (current user query)
    last_msg = conv_msgs[-1]
    last_cost = estimate_messages_tokens([last_msg])
    remaining_budget -= last_cost

    if remaining_budget <= 0:
        return system_msgs + [last_msg]

    # Fill from most recent to oldest
    kept_msgs: List[Dict[str, str]] = []
    for msg in reversed(conv_msgs[:-1]):
        msg_cost = estimate_messages_tokens([msg])
        if msg_cost <= remaining_budget:
            kept_msgs.insert(0, msg)
            remaining_budget -= msg_cost
        else:
            break  # stop once we can't fit the next oldest message

    return system_msgs + kept_msgs + [last_msg]


def truncate_rag_context(
    chunks: List[Dict],
    token_budget: int,
) -> List[Dict]:
    """Truncate RAG context chunks to fit within token budget.

    Chunks are assumed to be sorted by relevance (best first).
    Keeps as many top-scoring chunks as fit within the budget.
    """
    if not chunks or token_budget <= 0:
        return []

    kept: List[Dict] = []
    used = 0
    for chunk in chunks:
        chunk_tokens = estimate_tokens(chunk.get("content", ""))
        if used + chunk_tokens > token_budget:
            break
        kept.append(chunk)
        used += chunk_tokens

    return kept
