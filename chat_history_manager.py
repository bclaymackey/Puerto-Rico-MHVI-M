from datetime import datetime

import pandas as pd

# Single source of truth for chat history. NOTE: in-memory only —
# history is wiped on server restart. Acceptable for single-process
# local Dash. TODO: for multi-worker production deployment, replace
# this with Redis or a real database (sessions would otherwise be
# isolated per worker process and lost on restart).
_history_df = pd.DataFrame(columns=["session_id", "role", "content", "timestamp"])


def _append_row(session_id: str, role: str, content: str) -> None:
    global _history_df
    new_row = pd.DataFrame([{
        "session_id": session_id,
        "role": role,
        "content": content,
        "timestamp": datetime.utcnow(),
    }])
    _history_df = pd.concat([_history_df, new_row], ignore_index=True)


def build_llm_context(
    session_id: str,
    user_message: str,
    max_turns: int = 30,
) -> list[dict]:
    """Append the latest user message and return recent history for the LLM.

    Returns a list of {"role", "content"} dicts — no timestamps, no session_id.
    """
    _append_row(session_id, "user", user_message)

    session_rows = _history_df[_history_df["session_id"] == session_id]
    tail = session_rows.tail(max_turns * 2)

    llm_context = [
        {"role": row["role"], "content": row["content"]}
        for _, row in tail.iterrows()
    ]
    print("[build_llm_context]", session_id, llm_context)
    return llm_context


def save_ai_response(session_id: str, ai_message: str) -> None:
    _append_row(session_id, "assistant", ai_message)
    print("[save_ai_response]", session_id, ai_message)


def get_history_for_display(session_id: str) -> list[dict]:
    """Return history in the {role, text} shape used by the UI and PDF export."""
    session_rows = _history_df[_history_df["session_id"] == session_id]
    return [
        {"role": row["role"], "text": row["content"]}
        for _, row in session_rows.iterrows()
    ]


def clear_session(session_id: str) -> None:
    global _history_df
    _history_df = _history_df[_history_df["session_id"] != session_id].reset_index(drop=True)
