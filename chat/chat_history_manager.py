from mongodb import chat_dal
from .hyperparameters import CROSS_SESSION_MESSAGE_WINDOW, HISTORY_WINDOW
from .lexical_search import search_cross_session_memory

# Single source of truth for chat history, persisted in MongoDB (messages
# collection). Session/user rows are ensured by ai_service before messages are
# written. DB access is delegated to mongodb.chat_dal; this module keeps the
# prompt-assembly / language-backfill orchestration.

# Tuning lives in hyperparameters.py; aliased here for local readability.
_HISTORY_WINDOW = HISTORY_WINDOW
_CROSS_SESSION_MESSAGE_WINDOW = CROSS_SESSION_MESSAGE_WINDOW


def build_llm_context(
    session_id: str,
    user_message: str,
    max_turns: int = 30,
    language: str = "en",
) -> list[dict]:
    """Append the latest user message and return recent history for the LLM.

    Returns the most recent _HISTORY_WINDOW messages in chronological order as
    {"role", "content"} dicts.
    """
    chat_dal.append_row(session_id, "user", user_message, language)
    llm_context = chat_dal.build_llm_history(session_id, _HISTORY_WINDOW)
    print("[build_llm_context]", session_id, llm_context)
    return llm_context


def build_cross_session_memory_context(
    session_id: str,
    user_id: str | None,
    user_message: str,
    max_messages: int = _CROSS_SESSION_MESSAGE_WINDOW,
    entity_terms: list[str] | None = None,
) -> str:
    """Return lexically matched memory blocks from the same user's other sessions."""
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


def set_last_user_message_languages(
    session_id: str, content_en: str | None, content_es: str | None
) -> None:
    """Fill both language columns on the most recent user message of a session."""
    chat_dal.set_last_user_message_languages(session_id, content_en, content_es)


def save_ai_response(session_id: str, ai_message: str, language: str = "en") -> None:
    """Save a single-language assistant reply (short/templated flows)."""
    chat_dal.append_row(session_id, "assistant", ai_message, language)
    print("[save_ai_response]", session_id, ai_message)


def save_ai_response_bilingual(
    session_id: str,
    text_en: str,
    text_es: str,
    language: str = "en",
    title_en: str | None = None,
    title_es: str | None = None,
) -> None:
    """Save an assistant reply that already has both languages (main chat call)."""
    active = text_es if language == "es" else text_en
    chat_dal.append_row(
        session_id, "assistant", active, language,
        content_en=text_en, content_es=text_es,
    )
    chat_dal.set_llm_title(session_id, title_en, title_es)
    print("[save_ai_response_bilingual]", session_id, {"en": text_en, "es": text_es})


def backfill_session_language(session_id: str, language: str) -> None:
    """Translate & cache any rows missing the target language for this session.

    The main chat reply and its title already arrive bilingual (one LLM call),
    so this only fills the gaps: the user's typed messages, short templated
    replies, a user rename, the pre-reply placeholder title, or legacy rows.
    """
    # Imported lazily so the translator's OpenAI client isn't required for pure
    # read paths that never hit a missing column.
    from .translator import translate_text

    target_lang = "es" if language == "es" else "en"
    target_col = f"content_{target_lang}"

    for message_id, source_text in chat_dal.rows_missing_language(session_id, target_col):
        translated = translate_text(source_text, target_lang)
        chat_dal.update_message_language(message_id, target_col, translated)

    # Backfill the session's auto/custom titles in this language too.
    suffix = target_lang
    for base in ("auto_title", "custom_title"):
        source = chat_dal.session_title_source(session_id, base, suffix)
        if source:
            translated_title = chat_dal._title(translate_text(source, target_lang))
            chat_dal.update_session_title_language(
                session_id, f"{base}_{suffix}", translated_title
            )


def get_history_for_display(session_id: str, language: str = "en") -> list[dict]:
    """Return history in the {role, text} shape used by the UI and PDF export.

    Ensures the requested language exists for every row (lazy translate + cache),
    then returns that language's text.
    """
    backfill_session_language(session_id, language)
    return chat_dal.history_for_display(session_id, language)


def clear_session(session_id: str) -> None:
    chat_dal.clear_session(session_id)
