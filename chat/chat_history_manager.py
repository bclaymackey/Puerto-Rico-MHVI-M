from datetime import datetime
import re

from .chat_db import get_chat_db_connection
from .hyperparameters import CROSS_SESSION_MESSAGE_WINDOW, HISTORY_WINDOW
from .lexical_search import search_cross_session_memory
from .translator import make_bilingual

# Single source of truth for chat history, persisted in chat.db (messages table).
# Session/user rows are ensured by ai_service before messages are written.

# Tuning lives in hyperparameters.py; aliased here for local readability.
_HISTORY_WINDOW = HISTORY_WINDOW
_CROSS_SESSION_MESSAGE_WINDOW = CROSS_SESSION_MESSAGE_WINDOW


def _append_row(session_id: str, role: str, content: str, language: str = "en") -> None:
    """Insert a message, storing it in both English and Spanish.

    `language` is the language the message was written in (the active UI
    language). The original text is kept verbatim in its own language column and
    `content`; the other language column is filled by translation.
    """
    event_at = datetime.utcnow().isoformat()
    source_lang = "es" if language == "es" else "en"
    content_en, content_es = make_bilingual(content, source_lang)
    conn = get_chat_db_connection()
    try:
        conn.execute(
            "INSERT INTO messages "
            "(session_id, role, content, content_en, content_es, source_lang, timestamp) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (session_id, role, content, content_en, content_es, source_lang, event_at),
        )
        conn.execute(
            "UPDATE sessions SET updated_at = ? WHERE id = ?",
            (event_at, session_id),
        )
        if role == "user":
            title_en = re.sub(r"\s+", " ", (content_en or "").strip())[:80].rstrip()
            title_es = re.sub(r"\s+", " ", (content_es or "").strip())[:80].rstrip()
            if title_en or title_es:
                conn.execute(
                    """
                    UPDATE sessions
                    SET auto_title_en = CASE
                            WHEN COALESCE(NULLIF(TRIM(custom_title_en), ''),
                                          NULLIF(TRIM(auto_title_en), '')) IS NULL
                            THEN ? ELSE auto_title_en END,
                        auto_title_es = CASE
                            WHEN COALESCE(NULLIF(TRIM(custom_title_es), ''),
                                          NULLIF(TRIM(auto_title_es), '')) IS NULL
                            THEN ? ELSE auto_title_es END
                    WHERE id = ?
                    """,
                    (title_en, title_es, session_id),
                )
        conn.commit()
    finally:
        conn.close()


def build_llm_context(
    session_id: str,
    user_message: str,
    max_turns: int = 30,
    language: str = "en",
) -> list[dict]:
    """Append the latest user message and return recent history for the LLM.

    Returns a list of {"role", "content"} dicts — the most recent
    _HISTORY_WINDOW messages in chronological order.
    """
    _append_row(session_id, "user", user_message, language)

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
    entity_terms: list[str] | None = None,
) -> str:
    """Return lexically matched memory blocks from the same user's other sessions.

    `entity_terms` (active municipalities/category for this turn) boost pairs
    that mention them, so retrieval is entity-aware, not purely lexical.
    """
    result = search_cross_session_memory(
        session_id=session_id,
        user_id=user_id,
        user_message=user_message,
        max_messages=max_messages,
        entity_terms=entity_terms,
    )
    print("[cross_session_search]", {"session_id": session_id, "user_id": user_id, **result.search_payload()})
    print("[cross_session_db_hits]", result.db_hits_payload())
    print("[cross_session_selected_pairs]", result.selected_pairs_payload())
    print("[cross_session_memory_context]", result.memory_context or "<empty>")
    return result.memory_context


def save_ai_response(session_id: str, ai_message: str, language: str = "en") -> None:
    _append_row(session_id, "assistant", ai_message, language)
    print("[save_ai_response]", session_id, ai_message)


def get_history_for_display(session_id: str, language: str = "en") -> list[dict]:
    """Return history in the {role, text} shape used by the UI and PDF export.

    Text is returned in `language`, falling back to the original `content` for
    any legacy row written before bilingual storage existed.
    """
    text_column = "content_es" if language == "es" else "content_en"
    conn = get_chat_db_connection()
    try:
        rows = conn.execute(
            f"""
            SELECT id, role, COALESCE(NULLIF({text_column}, ''), content), timestamp
            FROM messages
            WHERE session_id = ?
            ORDER BY id
            """,
            (session_id,),
        ).fetchall()
    finally:
        conn.close()
    return [
        {
            "id": message_id,
            "role": role,
            "text": content,
            "timestamp": timestamp,
        }
        for message_id, role, content, timestamp in rows
    ]


def clear_session(session_id: str) -> None:
    conn = get_chat_db_connection()
    try:
        conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        conn.commit()
    finally:
        conn.close()
