"""Prompt-context assembler (context engineering).

One function per context layer is defined elsewhere; this module stitches them
together in priority order for a standard data turn. This is the single home for
layer assembly so ai_service stays thin and each layer stays independently
testable.

Layers:
  1. Most recent query        -> the raw user_input (passed through)
  2. Session history (8-12)    -> build_llm_context()        [chat.db, this session]
  3. Rolling session summary   -> get_session_summary()      [sessions.running_summary]
  4. Cross-session memory      -> build_cross_session_memory_context()  [lexical_search]
  5. Data context (the numbers)-> get_data_context()         [pr_dashboard.db, entity-aware]
  6. User name                 -> get_user_name()            [users.name]
"""

from .chat_db import get_session_summary, get_user_name
from .chat_history_manager import (
    build_cross_session_memory_context,
    build_llm_context,
)
from .conversation_state import resolve_active_entities
from .data_context_builder import get_data_context
from .hyperparameters import (
    CHARS_PER_TOKEN,
    CONTEXT_BUDGET_WEIGHTS,
    MAX_CONTEXT_TOKENS,
)
from .prompt import SYSTEM_PROMPT


def _char_budget(weight_key: str, available_tokens: int) -> int:
    """Char allowance for one variable layer from the shared token budget."""
    weight = CONTEXT_BUDGET_WEIGHTS.get(weight_key, 0.0)
    return int(available_tokens * weight) * CHARS_PER_TOKEN


def _trim_text(text: str, char_limit: int) -> str:
    if not text or len(text) <= char_limit:
        return text or ""
    return text[:char_limit].rstrip() + "…"


def _trim_history(history: list[dict], char_limit: int) -> list[dict]:
    """Keep the most recent turns that fit; drop oldest first."""
    kept: list[dict] = []
    used = 0
    for msg in reversed(history):
        size = len(msg.get("content") or "")
        if used + size > char_limit and kept:
            break
        kept.append(msg)
        used += size
    kept.reverse()
    return kept


def _apply_context_budget(ctx: dict) -> dict:
    """Cap the whole assembled prompt at MAX_CONTEXT_TOKENS by trimming each
    variable layer to its proportional share. The fixed system prompt is
    reserved first; the remaining budget is split by CONTEXT_BUDGET_WEIGHTS.
    """
    system_tokens = len(SYSTEM_PROMPT) // CHARS_PER_TOKEN
    available = max(0, MAX_CONTEXT_TOKENS - system_tokens)

    ctx["summary_context"] = _trim_text(
        ctx["summary_context"], _char_budget("summary_context", available)
    )
    ctx["memory_context"] = _trim_text(
        ctx["memory_context"], _char_budget("memory_context", available)
    )
    ctx["data_context"] = _trim_text(
        ctx["data_context"], _char_budget("data_context", available)
    )
    ctx["history"] = _trim_history(
        ctx["history"], _char_budget("history", available)
    )
    return ctx


def _entity_terms(entities: dict) -> list[str]:
    """Lowercase single-word terms for the active municipalities + category.

    The lexical matcher scores per word, so multi-word names are split (e.g.
    "San Juan" -> "san", "juan"); short stopword-like fragments are dropped.
    """
    terms: list[str] = []
    for m in entities.get("municipalities", []):
        terms.extend(m["name"].lower().split())
    table, display = entities.get("category") or (None, None)
    if display:
        terms.extend(display.lower().split())
    # Dedupe, keep only meaningful tokens.
    seen = set()
    cleaned = []
    for t in terms:
        t = t.strip()
        if len(t) < 3 or t in seen:
            continue
        seen.add(t)
        cleaned.append(t)
    return cleaned


def build_prompt_context(
    session_id: str,
    user_id: str | None,
    user_input: str,
    language: str = "en",
) -> dict:
    """Assemble all context layers for one standard turn.

    Returns the pieces ai_service spreads into call_llm. Note build_llm_context
    also appends the current user message to history (existing behavior).
    """
    # Layer 2 — recent raw turns (also records the user message).
    history = build_llm_context(session_id, user_input)

    # Layer 3 — rolling summary.
    summary_context = get_session_summary(session_id)["running_summary"] or ""

    # Resolve active entities once; reused by both retrieval (L4) and data (L5).
    entities = resolve_active_entities(session_id, user_input)
    entity_terms = _entity_terms(entities)

    # Layer 4 — cross-session memory, boosted toward the active entities.
    memory_context = build_cross_session_memory_context(
        session_id, user_id, user_input, entity_terms=entity_terms
    )

    # Layer 5 — data context, entity-aware so follow-ups resolve.
    data_context = get_data_context(
        user_input,
        language,
        active_munis=entities["municipalities"],
        active_category=entities["category"],
        wants_overall=entities["wants_overall"],
        wants_breakdown=entities["wants_breakdown"],
    )

    ctx = {
        "history": history,
        "summary_context": summary_context,
        "memory_context": memory_context,
        "data_context": data_context,
        "user_name": get_user_name(user_id),  # Layer 6
    }
    return _apply_context_budget(ctx)
