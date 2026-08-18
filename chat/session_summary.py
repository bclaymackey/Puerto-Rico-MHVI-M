"""Rolling per-session summary (Layer 3 of the prompt context).

Keeps a short running summary of the conversation so long threads stay coherent
without resending the full history every turn. Gated: only summarizes once a few
new messages have accumulated, so it adds roughly one LLM call per several
turns — not per turn. Reuses the configured provider and model.
"""

from mongodb import chat_dal
from .chat_db import get_session_summary, update_session_summary
from .hyperparameters import (
    SUMMARY_TRIGGER_MESSAGES as _SUMMARY_TRIGGER_MESSAGES,
    SUMMARY_WORD_LIMIT as _SUMMARY_WORD_LIMIT,
)
from .llm_caller import call_text_llm

_SUMMARY_INSTRUCTIONS = (
    "You maintain a running summary of a chat between a user and an assistant in "
    "a Puerto Rico mental health vulnerability dashboard. Update the summary with "
    f"the new turns. Keep it under {_SUMMARY_WORD_LIMIT} words. Track the active "
    "municipalities, the active category/domain, any comparison context, the "
    "user's preferred name if stated, and facts already resolved (so they are not "
    "re-asked). Output only the updated summary text, no preamble."
)


def _new_messages(session_id: str, after_id: int) -> list[tuple[int, str, str]]:
    return chat_dal.new_messages_after(session_id, after_id)


def maybe_update_summary(session_id: str) -> None:
    """Refresh the rolling summary if enough new messages have accumulated."""
    state = get_session_summary(session_id)
    last_id = state["last_summarized_message_id"] or 0
    new_rows = _new_messages(session_id, last_id)
    if len(new_rows) < _SUMMARY_TRIGGER_MESSAGES:
        return

    previous_summary = state["running_summary"] or "(none yet)"
    transcript = "\n".join(
        f"{role}: {content}" for _, role, content in new_rows if content
    )
    latest_id = new_rows[-1][0]

    user_input = (
        f"Previous summary:\n{previous_summary}\n\n"
        f"New turns:\n{transcript}"
    )

    try:
        summary = call_text_llm(_SUMMARY_INSTRUCTIONS, user_input)
    except Exception as e:
        print(f"[maybe_update_summary] error: {e}")
        return

    if summary:
        update_session_summary(session_id, summary, latest_id)
        print("[session_summary]", session_id, summary)
