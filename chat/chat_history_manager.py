from datetime import datetime

from .chat_db import get_chat_db_connection
from .lexical_search import search_cross_session_memory

# Single source of truth for chat history, persisted in chat.db (messages table).
# Session/user rows are ensured by ai_service before messages are written.

# Number of most recent messages (user + assistant combined) sent to the LLM.
_HISTORY_WINDOW = 20
_CROSS_SESSION_MESSAGE_WINDOW = 40


def _append_row(session_id: str, role: str, content: str) -> None:
    conn = get_chat_db_connection()
    try:
        conn.execute(
            "INSERT INTO messages (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
            (session_id, role, content, datetime.utcnow().isoformat()),
        )
        conn.commit()
    finally:
        conn.close()


def build_llm_context(
    session_id: str,
    user_message: str,
    max_turns: int = 30,
) -> list[dict]:
    """Append the latest user message and return recent history for the LLM.

    Returns a list of {"role", "content"} dicts — the most recent
    _HISTORY_WINDOW messages in chronological order.
    """
    _append_row(session_id, "user", user_message)

    conn = get_chat_db_connection()
    try:
        rows = conn.execute(
            "SELECT role, content FROM messages WHERE session_id = ? "
            "ORDER BY id DESC LIMIT ?",
            (session_id, _HISTORY_WINDOW),
        ).fetchall()
    finally:
        conn.close()

    # Rows come back newest-first; reverse to chronological for the LLM.
    llm_context = [{"role": role, "content": content} for role, content in reversed(rows)]
    print("[build_llm_context]", session_id, llm_context)
    return llm_context


def build_cross_session_memory_context(
    session_id: str,
    user_id: str | None,
    user_message: str,
    max_messages: int = _CROSS_SESSION_MESSAGE_WINDOW,
) -> str:
    """Return lexically matched memory blocks from the same user's other sessions."""
    result = search_cross_session_memory(
        session_id=session_id,
        user_id=user_id,
        user_message=user_message,
        max_messages=max_messages,
    )
    print("[cross_session_search]", {"session_id": session_id, "user_id": user_id, **result.search_payload()})
    print("[cross_session_db_hits]", result.db_hits_payload())
    print("[cross_session_selected_pairs]", result.selected_pairs_payload())
    print("[cross_session_memory_context]", result.memory_context or "<empty>")
    return result.memory_context


def save_ai_response(session_id: str, ai_message: str) -> None:
    _append_row(session_id, "assistant", ai_message)
    print("[save_ai_response]", session_id, ai_message)


def get_history_for_display(session_id: str) -> list[dict]:
    """Return history in the {role, text} shape used by the UI and PDF export."""
    conn = get_chat_db_connection()
    try:
        rows = conn.execute(
            "SELECT role, content FROM messages WHERE session_id = ? ORDER BY id",
            (session_id,),
        ).fetchall()
    finally:
        conn.close()
    return [{"role": role, "text": content} for role, content in rows]


def clear_session(session_id: str) -> None:
    conn = get_chat_db_connection()
    try:
        conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        conn.commit()
    finally:
        conn.close()
