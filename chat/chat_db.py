"""Chat DB public API.

Storage moved from SQLite (chat.db) to MongoDB. All logic now lives in the
modular ``mongodb`` package; this module re-exports the same function names so
callers (ai_service, callbacks, prompt_context, …) are unchanged.
"""

from mongodb.chat_dal import (
    delete_all_user_data,
    delete_session,
    ensure_session,
    ensure_user,
    get_session_summary,
    get_session_title,
    get_user_name,
    init_chat_db,
    list_user_sessions,
    rename_session,
    search_user_conversations,
    set_user_name,
    update_session_summary,
)

__all__ = [
    "delete_all_user_data",
    "delete_session",
    "ensure_session",
    "ensure_user",
    "get_session_summary",
    "get_session_title",
    "get_user_name",
    "init_chat_db",
    "list_user_sessions",
    "rename_session",
    "search_user_conversations",
    "set_user_name",
    "update_session_summary",
]

# Create indexes / seed the message counter at import time (mirrors the old
# init_chat_db() call that ran on import).
init_chat_db()
