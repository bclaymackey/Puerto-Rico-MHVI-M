"""Chat data-access layer, ported from SQLite (chat/chat.db) to MongoDB.

This module owns every read/write against the chat collections. The chat.* DB
modules (chat_db, chat_history_manager, session_summary, lexical_search) delegate
here, so their public function signatures — and therefore the orchestration layer
(ai_service, prompt_context, callbacks) — are unchanged.

Documents (see mongodb.client):
  users     {_id: user_id,   email, name}
  sessions  {_id: session_id, user_id, created_at, updated_at, auto_title,
             custom_title, running_summary, summary_updated_at,
             last_summarized_message_id, auto_title_en/_es, custom_title_en/_es}
  messages  {_id: int, session_id, role, content, content_en, content_es,
             source_lang, timestamp}
  counters  {_id: "messages", seq: int}   -- backs the integer message id
"""

import re
from datetime import datetime

from .client import counters, messages, next_message_id, sessions, users

_EMPTY_CHAT_TITLE = "Empty chat"
_SESSION_TITLE_LIMIT = 80


# ── Pure-Python title helpers (identical to the old SQLite module) ──────────────

def _normalize_session_title(text: str | None) -> str:
    normalized = re.sub(r"\s+", " ", (text or "").strip())
    if not normalized:
        return ""
    return normalized[:_SESSION_TITLE_LIMIT].rstrip()


def _title(text: str | None) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())[:80].rstrip()


def _coalesce(*values: str | None) -> str | None:
    """First value that is neither None nor empty/whitespace (SQL COALESCE+NULLIF)."""
    for value in values:
        if value is not None and str(value).strip() != "":
            return value
    return None


def _display_session_title(custom_title, auto_title, first_user_title) -> str:
    custom = _normalize_session_title(custom_title)
    if custom:
        return custom
    auto = _normalize_session_title(auto_title)
    if auto:
        return auto
    return _normalize_session_title(first_user_title) or _EMPTY_CHAT_TITLE


def _suffix(language: str) -> str:
    return "es" if language == "es" else "en"


# ── Schema / init ───────────────────────────────────────────────────────────────

def init_chat_db() -> None:
    """Kept for API compatibility. Index/counter setup happens in client.init_chat_mongo()."""
    from .client import init_chat_mongo

    init_chat_mongo()


# ── users ───────────────────────────────────────────────────────────────────────

def ensure_user(user_id: str, email: str | None = None) -> None:
    if not user_id:
        return
    users.update_one(
        {"_id": user_id},
        {"$setOnInsert": {"email": email, "name": None}},
        upsert=True,
    )


def set_user_name(user_id: str, name: str) -> None:
    ensure_user(user_id)
    users.update_one({"_id": user_id}, {"$set": {"name": name}})


def get_user_name(user_id: str | None) -> str | None:
    if not user_id:
        return None
    doc = users.find_one({"_id": user_id}, {"name": 1})
    return doc.get("name") if doc else None


# ── sessions ────────────────────────────────────────────────────────────────────

def ensure_session(session_id: str, user_id: str | None) -> None:
    timestamp = datetime.utcnow().isoformat()
    sessions.update_one(
        {"_id": session_id},
        {
            "$setOnInsert": {
                "user_id": user_id,
                "created_at": timestamp,
                "updated_at": timestamp,
                "auto_title": None,
                "custom_title": None,
            }
        },
        upsert=True,
    )


def get_session_summary(session_id: str) -> dict:
    """{"running_summary": str|None, "last_summarized_message_id": int|None}."""
    doc = sessions.find_one(
        {"_id": session_id},
        {"running_summary": 1, "last_summarized_message_id": 1},
    )
    if not doc:
        return {"running_summary": None, "last_summarized_message_id": None}
    return {
        "running_summary": doc.get("running_summary"),
        "last_summarized_message_id": doc.get("last_summarized_message_id"),
    }


def update_session_summary(session_id: str, summary: str, last_message_id: int) -> None:
    sessions.update_one(
        {"_id": session_id},
        {
            "$set": {
                "running_summary": summary,
                "summary_updated_at": datetime.utcnow().isoformat(),
                "last_summarized_message_id": last_message_id,
            }
        },
    )


def _first_user_message_text(session_id: str, language: str) -> str | None:
    """Earliest user message's text in the target language (SQL correlated subquery)."""
    content_col = f"content_{_suffix(language)}"
    doc = messages.find_one(
        {"session_id": session_id, "role": "user"},
        {content_col: 1, "content": 1},
        sort=[("_id", 1)],
    )
    if not doc:
        return None
    return _coalesce(doc.get(content_col), doc.get("content"))


def get_session_title(session_id: str, language: str = "en") -> str:
    suffix = _suffix(language)
    doc = sessions.find_one(
        {"_id": session_id},
        {
            f"custom_title_{suffix}": 1, "custom_title": 1,
            f"auto_title_{suffix}": 1, "auto_title": 1,
        },
    )
    if not doc:
        return _EMPTY_CHAT_TITLE
    custom = _coalesce(doc.get(f"custom_title_{suffix}"), doc.get("custom_title"))
    auto = _coalesce(doc.get(f"auto_title_{suffix}"), doc.get("auto_title"))
    first_user = _first_user_message_text(session_id, language)
    return _display_session_title(custom, auto, first_user)


def rename_session(session_id: str, title: str | None, language: str = "en") -> None:
    if not session_id:
        return
    # Store the new title in the active language only; the other language is
    # filled lazily (translate + cache) the first time the session is viewed there.
    normalized = _normalize_session_title(title) or None
    suffix = _suffix(language)
    other = "en" if suffix == "es" else "es"
    sessions.update_one(
        {"_id": session_id},
        {
            "$set": {
                "custom_title": normalized,
                f"custom_title_{suffix}": normalized,
                f"custom_title_{other}": None,
            }
        },
    )


def _user_session_ids(user_id: str) -> list[str]:
    return [doc["_id"] for doc in sessions.find({"user_id": user_id}, {"_id": 1})]


def delete_all_user_data(user_id: str | None) -> None:
    """Delete every session, message, and summary for this user (used by /delete)."""
    if not user_id:
        return
    ids = _user_session_ids(user_id)
    if ids:
        messages.delete_many({"session_id": {"$in": ids}})
    sessions.delete_many({"user_id": user_id})


def delete_session(session_id: str, user_id: str | None = None) -> None:
    if not session_id:
        return
    if user_id:
        if not sessions.find_one({"_id": session_id, "user_id": user_id}, {"_id": 1}):
            return
    messages.delete_many({"session_id": session_id})
    sessions.delete_one({"_id": session_id})


def list_user_sessions(user_id: str | None, language: str = "en") -> list[dict]:
    if not user_id:
        return []
    suffix = _suffix(language)
    content_col = f"content_{suffix}"
    # LEFT JOIN + GROUP BY + HAVING count>0 + first-user-message subquery, as an
    # aggregation pipeline. Sort mirrors: updated_at desc, then created_at desc.
    pipeline = [
        {"$match": {"user_id": user_id}},
        {
            "$lookup": {
                "from": "messages",
                "localField": "_id",
                "foreignField": "session_id",
                "as": "_messages",
            }
        },
        {"$addFields": {"message_count": {"$size": "$_messages"}}},
        {"$match": {"message_count": {"$gt": 0}}},
        {
            "$addFields": {
                "updated_at_eff": {"$ifNull": ["$updated_at", "$created_at"]},
                "auto_title_disp": {"$ifNull": [f"$auto_title_{suffix}", "$auto_title"]},
                "custom_title_disp": {
                    "$ifNull": [f"$custom_title_{suffix}", "$custom_title"]
                },
            }
        },
        {"$sort": {"updated_at_eff": -1, "created_at": -1}},
        {"$project": {"_messages": 0}},
    ]
    result = []
    for doc in sessions.aggregate(pipeline):
        first_user = _first_user_message_text(doc["_id"], language)
        item = {
            "id": doc["_id"],
            "created_at": doc.get("created_at"),
            "updated_at": doc.get("updated_at_eff"),
            "auto_title": doc.get("auto_title_disp"),
            "custom_title": doc.get("custom_title_disp"),
            "message_count": doc.get("message_count", 0),
            "first_user_title": first_user,
        }
        item["title"] = _display_session_title(
            item["custom_title"], item["auto_title"], first_user
        )
        result.append(item)
    return result


def search_user_conversations(
    user_id: str | None,
    query: str,
    limit: int = 50,
    language: str = "en",
) -> list[dict]:
    normalized_query = _normalize_session_title(query).lower()
    if not user_id:
        return []
    if not normalized_query:
        return list_user_sessions(user_id, language)[:limit]

    session_items = list_user_sessions(user_id, language)
    if not session_items:
        return []

    suffix = _suffix(language)
    content_col = f"content_{suffix}"
    session_ids = [s["id"] for s in session_items]

    # Case-insensitive substring match on the target-language column, falling back
    # to the source `content` — matches the old LOWER(...) LIKE '%q%'.
    pattern = re.escape(normalized_query)
    cursor = messages.find(
        {
            "session_id": {"$in": session_ids},
            "$or": [
                {content_col: {"$regex": pattern, "$options": "i"}},
                {"content": {"$regex": pattern, "$options": "i"}},
            ],
        },
        {"session_id": 1, "role": 1, content_col: 1, "content": 1, "timestamp": 1},
        sort=[("timestamp", -1), ("_id", -1)],
    )

    message_matches: dict[str, list[dict]] = {}
    for doc in cursor:
        text = _coalesce(doc.get(content_col), doc.get("content")) or ""
        if normalized_query not in text.lower():
            continue  # regex is diacritic-loose; enforce the exact substring like SQL LOWER LIKE
        message_matches.setdefault(doc["session_id"], []).append(
            {
                "message_id": doc["_id"],
                "role": doc["role"],
                "content": text,
                "timestamp": doc.get("timestamp"),
            }
        )

    results = []
    for session in session_items:
        title_match = normalized_query in session["title"].lower()
        matches = message_matches.get(session["id"], [])
        if not title_match and not matches:
            continue
        first_match = matches[0] if matches else None
        preview_source = first_match["content"] if first_match else session["title"]
        match_count = len(matches) + (1 if title_match else 0)
        results.append(
            {
                **session,
                "match_message_id": first_match["message_id"] if first_match else None,
                "match_preview": _normalize_session_title(preview_source),
                "match_role": first_match["role"] if first_match else None,
                "match_timestamp": first_match["timestamp"] if first_match else None,
                "match_count": match_count,
                "title_match": title_match,
            }
        )

    results.sort(
        key=lambda item: (
            item.get("match_count", 0),
            1 if item.get("title_match") else 0,
            item.get("updated_at") or item.get("created_at") or "",
        ),
        reverse=True,
    )
    return results[:limit]


# ── messages (write) ────────────────────────────────────────────────────────────

def append_row(
    session_id: str,
    role: str,
    content: str,
    language: str = "en",
    content_en: str | None = None,
    content_es: str | None = None,
) -> None:
    """Insert a message with whatever language copies we already have.

    No translation call happens here. `content` is the source text in `language`.
    """
    event_at = datetime.utcnow().isoformat()
    source_lang = "es" if language == "es" else "en"
    if content_en is None and content_es is None:
        content_en = content if source_lang == "en" else None
        content_es = content if source_lang == "es" else None

    messages.insert_one(
        {
            "_id": next_message_id(),
            "session_id": session_id,
            "role": role,
            "content": content,
            "content_en": content_en,
            "content_es": content_es,
            "source_lang": source_lang,
            "timestamp": event_at,
        }
    )
    sessions.update_one({"_id": session_id}, {"$set": {"updated_at": event_at}})

    if role == "user":
        # Seed a placeholder auto-title from the user's first message, unless one
        # is already set (COALESCE(NULLIF(TRIM(seed_col),''), ?)).
        seed_col = f"auto_title_{source_lang}"
        seed = _title(content_es if source_lang == "es" else content_en)
        if seed:
            current = sessions.find_one({"_id": session_id}, {seed_col: 1})
            if not current or not (current.get(seed_col) or "").strip():
                sessions.update_one({"_id": session_id}, {"$set": {seed_col: seed}})


def build_llm_history(session_id: str, history_window: int) -> list[dict]:
    """Recent history for the LLM: last N messages in chronological order."""
    docs = list(
        messages.find(
            {"session_id": session_id},
            {"role": 1, "content": 1},
            sort=[("_id", -1)],
        ).limit(history_window)
    )
    return [{"role": d["role"], "content": d["content"]} for d in reversed(docs)]


def set_last_user_message_languages(
    session_id: str, content_en: str | None, content_es: str | None
) -> None:
    """Fill both language columns on the most recent user message of a session."""
    if not (content_en or content_es):
        return
    doc = messages.find_one(
        {"session_id": session_id, "role": "user"},
        {"_id": 1, "content_en": 1, "content_es": 1},
        sort=[("_id", -1)],
    )
    if not doc:
        return
    set_fields = {}
    if not (doc.get("content_en") or "").strip() and content_en:
        set_fields["content_en"] = content_en
    if not (doc.get("content_es") or "").strip() and content_es:
        set_fields["content_es"] = content_es
    if set_fields:
        messages.update_one({"_id": doc["_id"]}, {"$set": set_fields})


def set_llm_title(session_id: str, title_en: str | None, title_es: str | None) -> None:
    """Set the LLM-generated bilingual auto-title, unless a custom title is set."""
    title_en = _title(title_en)
    title_es = _title(title_es)
    if not title_en and not title_es:
        return
    doc = sessions.find_one(
        {"_id": session_id}, {"custom_title_en": 1, "custom_title_es": 1}
    )
    if doc is None:
        return
    set_fields = {}
    if title_en and not (doc.get("custom_title_en") or "").strip():
        set_fields["auto_title_en"] = title_en
    if title_es and not (doc.get("custom_title_es") or "").strip():
        set_fields["auto_title_es"] = title_es
    if set_fields:
        sessions.update_one({"_id": session_id}, {"$set": set_fields})


def clear_session(session_id: str) -> None:
    messages.delete_many({"session_id": session_id})


# ── messages (read) ─────────────────────────────────────────────────────────────

def rows_missing_language(session_id: str, target_col: str) -> list[tuple[int, str]]:
    """(id, source_text) for rows whose target-language column is empty."""
    docs = messages.find(
        {"session_id": session_id},
        {"content_en": 1, "content_es": 1, "content": 1, target_col: 1},
        sort=[("_id", 1)],
    )
    result = []
    for doc in docs:
        if (doc.get(target_col) or "").strip():
            continue
        source = _coalesce(doc.get("content_en"), doc.get("content_es"), doc.get("content"))
        result.append((doc["_id"], source))
    return result


def update_message_language(message_id: int, target_col: str, translated: str) -> None:
    messages.update_one({"_id": message_id}, {"$set": {target_col: translated}})


def session_title_source(session_id: str, base: str, suffix: str):
    """Source text to translate for a missing auto_/custom_ title, or None."""
    col = f"{base}_{suffix}"
    doc = sessions.find_one(
        {"_id": session_id}, {f"{base}_en": 1, f"{base}_es": 1, col: 1}
    )
    if not doc or (doc.get(col) or "").strip():
        return None
    return _coalesce(doc.get(f"{base}_en"), doc.get(f"{base}_es"))


def update_session_title_language(session_id: str, col: str, translated: str) -> None:
    sessions.update_one({"_id": session_id}, {"$set": {col: translated}})


def history_for_display(session_id: str, language: str) -> list[dict]:
    text_col = f"content_{_suffix(language)}"
    docs = messages.find(
        {"session_id": session_id},
        {"role": 1, text_col: 1, "content": 1, "timestamp": 1},
        sort=[("_id", 1)],
    )
    return [
        {
            "id": doc["_id"],
            "role": doc["role"],
            "text": _coalesce(doc.get(text_col), doc.get("content")),
            "timestamp": doc.get("timestamp"),
        }
        for doc in docs
    ]


# ── session_summary support ─────────────────────────────────────────────────────

def new_messages_after(session_id: str, after_id: int) -> list[tuple[int, str, str]]:
    docs = messages.find(
        {"session_id": session_id, "_id": {"$gt": after_id}},
        {"role": 1, "content": 1},
        sort=[("_id", 1)],
    )
    return [(doc["_id"], doc["role"], doc["content"]) for doc in docs]


# ── conversation_state support ──────────────────────────────────────────────────

def recent_session_message_contents(session_id: str, limit: int) -> list[str]:
    docs = messages.find(
        {"session_id": session_id}, {"content": 1}, sort=[("_id", -1)]
    ).limit(limit)
    return [(doc.get("content") or "") for doc in docs]


# ── lexical_search support (cross-session retrieval) ────────────────────────────

def recent_other_session_ids(session_id: str, user_id: str, limit: int) -> list[str]:
    docs = sessions.find(
        {"user_id": user_id, "_id": {"$ne": session_id}},
        {"_id": 1},
        sort=[("created_at", -1)],
    ).limit(limit)
    return [doc["_id"] for doc in docs]


def messages_for_sessions(session_ids: list[str]) -> dict[str, list[dict]]:
    """All messages for the given sessions, grouped by session, ordered by id.

    event_at = timestamp or the session's created_at (SQL COALESCE alias).
    """
    if not session_ids:
        return {}
    session_created = {
        doc["_id"]: doc.get("created_at")
        for doc in sessions.find({"_id": {"$in": session_ids}}, {"created_at": 1})
    }
    docs = messages.find(
        {"session_id": {"$in": session_ids}},
        {"session_id": 1, "role": 1, "content": 1, "timestamp": 1},
        sort=[("session_id", 1), ("_id", 1)],
    )
    grouped: dict[str, list[dict]] = {}
    for doc in docs:
        sid = doc["session_id"]
        grouped.setdefault(sid, []).append(
            {
                "id": doc["_id"],
                "session_id": sid,
                "role": doc["role"],
                "event_at": doc.get("timestamp") or session_created.get(sid),
                "content": doc.get("content") or "",
            }
        )
    return grouped


def text_search_candidates(session_ids: list[str], search_text: str) -> list[dict]:
    """Candidate messages via the $text index, restricted to the given sessions.

    Replaces the SQLite UDF-scored SELECT. Scoring/ranking stays in Python
    (lexical_search); this only fetches candidates. Falls back to all messages
    in the sessions if the search string is empty.
    """
    if not session_ids:
        return []
    session_created = {
        doc["_id"]: doc.get("created_at")
        for doc in sessions.find({"_id": {"$in": session_ids}}, {"created_at": 1})
    }
    query: dict = {"session_id": {"$in": session_ids}}
    if search_text.strip():
        query["$text"] = {"$search": search_text}
    docs = messages.find(
        query,
        {"session_id": 1, "role": 1, "content": 1, "timestamp": 1},
    )
    return [
        {
            "id": doc["_id"],
            "session_id": doc["session_id"],
            "role": doc["role"],
            "event_at": doc.get("timestamp") or session_created.get(doc["session_id"]),
            "content": doc.get("content") or "",
        }
        for doc in docs
    ]
