import sqlite3
from datetime import datetime
from pathlib import Path
import re


_EMPTY_CHAT_TITLE = "Empty chat"
_SESSION_TITLE_LIMIT = 80


def get_chat_db_connection() -> sqlite3.Connection:
    return sqlite3.connect(str(Path(__file__).parent / 'chat.db'))


def _normalize_session_title(text: str | None) -> str:
    normalized = re.sub(r"\s+", " ", (text or "").strip())
    if not normalized:
        return ""
    return normalized[:_SESSION_TITLE_LIMIT].rstrip()


def _row_value(row: sqlite3.Row | tuple, key: str, index: int):
    return row[key] if isinstance(row, sqlite3.Row) else row[index]


def _display_session_title(row: sqlite3.Row | tuple | None) -> str:
    if not row:
        return _EMPTY_CHAT_TITLE
    custom_title = _normalize_session_title(_row_value(row, "custom_title", 0))
    if custom_title:
        return custom_title
    auto_title = _normalize_session_title(_row_value(row, "auto_title", 1))
    if auto_title:
        return auto_title
    first_user_title = _normalize_session_title(_row_value(row, "first_user_title", 2))
    return first_user_title or _EMPTY_CHAT_TITLE


def init_chat_db() -> None:
    """Create the users / sessions / messages tables if they don't exist."""
    conn = get_chat_db_connection()
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT
            );

            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                user_id TEXT,
                created_at TEXT,
                updated_at TEXT,
                auto_title TEXT,
                custom_title TEXT,
                FOREIGN KEY (user_id) REFERENCES users (id)
            );

            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT,
                timestamp TEXT,
                FOREIGN KEY (session_id) REFERENCES sessions (id)
            );

            CREATE INDEX IF NOT EXISTS idx_sessions_user_created_at
                ON sessions (user_id, created_at DESC);

            CREATE INDEX IF NOT EXISTS idx_messages_session_id_id
                ON messages (session_id, id);

            CREATE INDEX IF NOT EXISTS idx_messages_session_role_id
                ON messages (session_id, role, id);
            """
        )
        columns = {row[1] for row in conn.execute("PRAGMA table_info(users)")}
        if "name" not in columns:
            conn.execute("ALTER TABLE users ADD COLUMN name TEXT")
        session_columns = {row[1] for row in conn.execute("PRAGMA table_info(sessions)")}
        if "updated_at" not in session_columns:
            conn.execute("ALTER TABLE sessions ADD COLUMN updated_at TEXT")
        if "auto_title" not in session_columns:
            conn.execute("ALTER TABLE sessions ADD COLUMN auto_title TEXT")
        if "custom_title" not in session_columns:
            conn.execute("ALTER TABLE sessions ADD COLUMN custom_title TEXT")
        if "running_summary" not in session_columns:
            conn.execute("ALTER TABLE sessions ADD COLUMN running_summary TEXT")
        if "summary_updated_at" not in session_columns:
            conn.execute("ALTER TABLE sessions ADD COLUMN summary_updated_at TEXT")
        if "last_summarized_message_id" not in session_columns:
            conn.execute(
                "ALTER TABLE sessions ADD COLUMN last_summarized_message_id INTEGER"
            )
        # ── Bilingual storage: every message/title/summary in both languages ──
        session_columns = {row[1] for row in conn.execute("PRAGMA table_info(sessions)")}
        for column in (
            "auto_title_en", "auto_title_es",
            "custom_title_en", "custom_title_es",
            "running_summary_en", "running_summary_es",
        ):
            if column not in session_columns:
                conn.execute(f"ALTER TABLE sessions ADD COLUMN {column} TEXT")
        message_columns = {row[1] for row in conn.execute("PRAGMA table_info(messages)")}
        for column in ("content_en", "content_es", "source_lang"):
            if column not in message_columns:
                conn.execute(f"ALTER TABLE messages ADD COLUMN {column} TEXT")
        conn.execute(
            """
            UPDATE sessions
            SET updated_at = COALESCE(updated_at, created_at)
            WHERE updated_at IS NULL
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_sessions_user_updated_at
            ON sessions (user_id, updated_at DESC, created_at DESC)
            """
        )
        conn.commit()
    finally:
        conn.close()


def ensure_user(user_id: str, email: str | None = None) -> None:
    conn = get_chat_db_connection()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO users (id, email) VALUES (?, ?)",
            (user_id, email),
        )
        conn.commit()
    finally:
        conn.close()


def ensure_session(session_id: str, user_id: str | None) -> None:
    timestamp = datetime.utcnow().isoformat()
    conn = get_chat_db_connection()
    try:
        conn.execute(
            """
            INSERT OR IGNORE INTO sessions (
                id, user_id, created_at, updated_at, auto_title, custom_title
            ) VALUES (?, ?, ?, ?, NULL, NULL)
            """,
            (session_id, user_id, timestamp, timestamp),
        )
        conn.commit()
    finally:
        conn.close()


def set_user_name(user_id: str, name: str) -> None:
    ensure_user(user_id)
    conn = get_chat_db_connection()
    try:
        conn.execute("UPDATE users SET name = ? WHERE id = ?", (name, user_id))
        conn.commit()
    finally:
        conn.close()


def get_user_name(user_id: str | None) -> str | None:
    if not user_id:
        return None
    conn = get_chat_db_connection()
    try:
        row = conn.execute("SELECT name FROM users WHERE id = ?", (user_id,)).fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def get_session_summary(session_id: str) -> dict:
    """Return the rolling summary state for a session.

    {"running_summary": str | None, "last_summarized_message_id": int | None}
    """
    conn = get_chat_db_connection()
    try:
        row = conn.execute(
            "SELECT running_summary, last_summarized_message_id "
            "FROM sessions WHERE id = ?",
            (session_id,),
        ).fetchone()
    finally:
        conn.close()
    if not row:
        return {"running_summary": None, "last_summarized_message_id": None}
    return {"running_summary": row[0], "last_summarized_message_id": row[1]}


def update_session_summary(
    session_id: str,
    summary: str,
    last_message_id: int,
    source_lang: str = "en",
) -> None:
    # Import here to avoid a circular import at module load (translator imports
    # llm_caller, which is otherwise independent of chat_db).
    from .translator import make_bilingual

    summary_en, summary_es = make_bilingual(summary, source_lang)
    conn = get_chat_db_connection()
    try:
        conn.execute(
            """
            UPDATE sessions
            SET running_summary = ?,
                running_summary_en = ?,
                running_summary_es = ?,
                summary_updated_at = ?,
                last_summarized_message_id = ?
            WHERE id = ?
            """,
            (
                summary, summary_en, summary_es,
                datetime.utcnow().isoformat(), last_message_id, session_id,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def get_session_title(session_id: str, language: str = "en") -> str:
    suffix = "es" if language == "es" else "en"
    content_col = f"content_{suffix}"
    conn = get_chat_db_connection()
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            f"""
            SELECT
                COALESCE(s.custom_title_{suffix}, s.custom_title) AS custom_title,
                COALESCE(s.auto_title_{suffix}, s.auto_title) AS auto_title,
                (
                    SELECT COALESCE(NULLIF({content_col}, ''), content)
                    FROM messages
                    WHERE session_id = s.id AND role = 'user'
                    ORDER BY id
                    LIMIT 1
                ) AS first_user_title
            FROM sessions AS s
            WHERE s.id = ?
            """,
            (session_id,),
        ).fetchone()
        return _display_session_title(row)
    finally:
        conn.close()


def rename_session(session_id: str, title: str | None, language: str = "en") -> None:
    if not session_id:
        return
    from .translator import make_bilingual

    normalized = _normalize_session_title(title)
    source_lang = "es" if language == "es" else "en"
    if normalized:
        title_en, title_es = make_bilingual(normalized, source_lang)
        title_en = _normalize_session_title(title_en) or None
        title_es = _normalize_session_title(title_es) or None
    else:
        title_en = title_es = None
    conn = get_chat_db_connection()
    try:
        conn.execute(
            """
            UPDATE sessions
            SET custom_title = ?, custom_title_en = ?, custom_title_es = ?
            WHERE id = ?
            """,
            (normalized or None, title_en, title_es, session_id),
        )
        conn.commit()
    finally:
        conn.close()


def delete_all_user_data(user_id: str | None) -> None:
    """Delete every session, message, and summary for this user (used by /delete)."""
    if not user_id:
        return
    conn = get_chat_db_connection()
    try:
        conn.execute(
            "DELETE FROM messages WHERE session_id IN "
            "(SELECT id FROM sessions WHERE user_id = ?)",
            (user_id,),
        )
        conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
        conn.commit()
    finally:
        conn.close()


def delete_session(session_id: str, user_id: str | None = None) -> None:
    if not session_id:
        return
    conn = get_chat_db_connection()
    try:
        if user_id:
            row = conn.execute(
                "SELECT 1 FROM sessions WHERE id = ? AND user_id = ?",
                (session_id, user_id),
            ).fetchone()
            if not row:
                return
        conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        conn.commit()
    finally:
        conn.close()


def list_user_sessions(user_id: str | None, language: str = "en") -> list[dict]:
    if not user_id:
        return []
    suffix = "es" if language == "es" else "en"
    content_col = f"content_{suffix}"
    conn = get_chat_db_connection()
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            f"""
            SELECT
                s.id,
                s.created_at,
                COALESCE(s.updated_at, s.created_at) AS updated_at,
                COALESCE(s.auto_title_{suffix}, s.auto_title) AS auto_title,
                COALESCE(s.custom_title_{suffix}, s.custom_title) AS custom_title,
                COUNT(m.id) AS message_count,
                (
                    SELECT COALESCE(NULLIF({content_col}, ''), content)
                    FROM messages
                    WHERE session_id = s.id AND role = 'user'
                    ORDER BY id
                    LIMIT 1
                ) AS first_user_title
            FROM sessions AS s
            LEFT JOIN messages AS m ON m.session_id = s.id
            WHERE s.user_id = ?
            GROUP BY s.id
            HAVING COUNT(m.id) > 0
            ORDER BY COALESCE(s.updated_at, s.created_at) DESC, s.created_at DESC
            """,
            (user_id,),
        ).fetchall()
        sessions = []
        for row in rows:
            item = dict(row)
            item["title"] = _display_session_title(row)
            sessions.append(item)
        return sessions
    finally:
        conn.close()


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

    sessions = list_user_sessions(user_id, language)
    if not sessions:
        return []

    suffix = "es" if language == "es" else "en"
    content_col = f"content_{suffix}"
    conn = get_chat_db_connection()
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            f"""
            SELECT
                m.session_id,
                m.id AS message_id,
                m.role,
                COALESCE(NULLIF(m.{content_col}, ''), m.content) AS content,
                m.timestamp
            FROM messages AS m
            JOIN sessions AS s ON s.id = m.session_id
            WHERE s.user_id = ?
              AND LOWER(COALESCE(NULLIF(m.{content_col}, ''), m.content, '')) LIKE ?
            ORDER BY COALESCE(m.timestamp, s.created_at) DESC, m.id DESC
            """,
            (user_id, f"%{normalized_query}%"),
        ).fetchall()
    finally:
        conn.close()

    message_matches: dict[str, list[dict]] = {}
    for row in rows:
        message_matches.setdefault(row["session_id"], []).append(
            {
                "message_id": row["message_id"],
                "role": row["role"],
                "content": row["content"] or "",
                "timestamp": row["timestamp"],
            }
        )

    results = []
    for session in sessions:
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


init_chat_db()
