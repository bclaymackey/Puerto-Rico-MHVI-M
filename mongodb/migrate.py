"""One-time ETL: chat/chat.db (SQLite) -> MongoDB.

Idempotent (upsert by _id), so it is safe to re-run. Preserves the integer
message ids and continues the counter past the highest imported id.

Run from the project root:
    python -m mongodb.migrate
"""

import sqlite3
from pathlib import Path

from .client import counters, messages, sessions, users

SQLITE_PATH = Path(__file__).resolve().parent.parent / "chat" / "chat.db"

# running_summary_en / running_summary_es are intentionally omitted (unused).
SESSION_FIELDS = [
    "id", "user_id", "created_at", "updated_at", "auto_title", "custom_title",
    "running_summary", "summary_updated_at", "last_summarized_message_id",
    "auto_title_en", "auto_title_es", "custom_title_en", "custom_title_es",
]
MESSAGE_FIELDS = [
    "id", "session_id", "role", "content", "timestamp",
    "content_en", "content_es", "source_lang",
]


def _existing_columns(conn, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def migrate() -> dict:
    if not SQLITE_PATH.exists():
        print(f"No SQLite chat DB at {SQLITE_PATH} — nothing to migrate.")
        return {"users": 0, "sessions": 0, "messages": 0, "max_id": 0}

    conn = sqlite3.connect(str(SQLITE_PATH))
    conn.row_factory = sqlite3.Row
    n_users = n_sessions = n_messages = 0
    max_id = 0
    try:
        for row in conn.execute("SELECT id, email, name FROM users"):
            users.update_one(
                {"_id": row["id"]},
                {"$set": {"email": row["email"], "name": row["name"]}},
                upsert=True,
            )
            n_users += 1

        session_cols = [c for c in SESSION_FIELDS if c in _existing_columns(conn, "sessions")]
        for row in conn.execute(f"SELECT {', '.join(session_cols)} FROM sessions"):
            doc = {c: row[c] for c in session_cols if c != "id"}
            sessions.update_one({"_id": row["id"]}, {"$set": doc}, upsert=True)
            n_sessions += 1

        message_cols = [c for c in MESSAGE_FIELDS if c in _existing_columns(conn, "messages")]
        for row in conn.execute(f"SELECT {', '.join(message_cols)} FROM messages"):
            doc = {c: row[c] for c in message_cols if c != "id"}
            messages.update_one({"_id": row["id"]}, {"$set": doc}, upsert=True)
            n_messages += 1
            max_id = max(max_id, row["id"])

        # Continue new ids past the highest imported id.
        counters.update_one(
            {"_id": "messages"}, {"$set": {"seq": max_id}}, upsert=True
        )
    finally:
        conn.close()

    print(
        f"Migrated {n_users} users, {n_sessions} sessions, {n_messages} messages; "
        f"counters.seq = {max_id}"
    )
    return {
        "users": n_users,
        "sessions": n_sessions,
        "messages": n_messages,
        "max_id": max_id,
    }


if __name__ == "__main__":
    migrate()
