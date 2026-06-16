import sqlite3
from datetime import datetime
from pathlib import Path


def get_chat_db_connection() -> sqlite3.Connection:
    return sqlite3.connect(str(Path(__file__).parent / 'chat.db'))


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
    conn = get_chat_db_connection()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO sessions (id, user_id, created_at) VALUES (?, ?, ?)",
            (session_id, user_id, datetime.utcnow().isoformat()),
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


def list_user_sessions(user_id: str | None) -> list[dict]:
    if not user_id:
        return []
    conn = get_chat_db_connection()
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT s.id, s.created_at, COUNT(m.id) AS message_count,
                   COALESCE((
                       SELECT content
                       FROM messages
                       WHERE session_id = s.id AND role = 'user'
                       ORDER BY id
                       LIMIT 1
                   ), 'Empty chat') AS title
            FROM sessions AS s
            LEFT JOIN messages AS m ON m.session_id = s.id
            WHERE s.user_id = ?
            GROUP BY s.id
            HAVING COUNT(m.id) > 0
            ORDER BY s.created_at DESC
            """,
            (user_id,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()
