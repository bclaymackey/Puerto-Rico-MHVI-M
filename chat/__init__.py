"""Chat assistant package: persistence, history, LLM, and report flows.

Public API used by the dashboard root (callbacks.py, MHVIM_Dashboard_App.py).
"""

from .ai_service import consume_report, process_chat_message
from .chat_db import (
    delete_session,
    get_session_title,
    init_chat_db,
    list_user_sessions,
    rename_session,
    search_user_conversations,
    set_user_name,
)
from .chat_history_manager import clear_session, get_history_for_display
from .pdf_export import build_pdf_bytes

__all__ = [
    "process_chat_message",
    "consume_report",
    "init_chat_db",
    "delete_session",
    "get_session_title",
    "list_user_sessions",
    "rename_session",
    "search_user_conversations",
    "set_user_name",
    "clear_session",
    "get_history_for_display",
    "build_pdf_bytes",
]
