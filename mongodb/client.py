"""MongoDB connection, collections, and low-level helpers for the chat database.

A single module-level MongoClient is used because PyMongo clients are
thread-safe and connection-pooled — there is no need for the per-call
open/close pattern SQLite required.
"""

import os

from dotenv import load_dotenv
from pymongo import ASCENDING, DESCENDING, TEXT, MongoClient, ReturnDocument
from pymongo.errors import PyMongoError

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
MONGODB_DB = os.getenv("MONGODB_DB", "pr_chat")

client = MongoClient(MONGODB_URI)
db = client[MONGODB_DB]

users = db.users
sessions = db.sessions
messages = db.messages
counters = db.counters


_logged_connection = False


def _log_connection() -> None:
    """Print a clear one-line banner confirming the chat DB backend on startup.

    Prints once per process — init_chat_mongo() may be called more than once
    (module import + explicit app startup).
    """
    global _logged_connection
    if _logged_connection:
        return
    _logged_connection = True
    try:
        info = client.server_info()  # forces a real round-trip to the server
        version = info.get("version", "?")
        host = client.address[0] if client.address else MONGODB_URI
        print(
            f"[chat-db] ✅ MongoDB connected — server v{version} "
            f"@ {host}, database '{MONGODB_DB}' (chat history: users/sessions/messages)"
        )
    except PyMongoError as exc:
        print(
            f"[chat-db] ❌ MongoDB NOT reachable at {MONGODB_URI} ({exc}). "
            "Start it with: brew services start mongodb-community"
        )


def next_message_id() -> int:
    """Dense monotonic integer id for a new message.

    Replaces SQLite's AUTOINCREMENT `messages.id`, which is load-bearing: it is
    used for chronological ordering, history windows, and the rolling-summary
    high-water mark (`last_summarized_message_id`). ObjectId is not a dense
    integer, so we keep our own counter.
    """
    doc = counters.find_one_and_update(
        {"_id": "messages"},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return doc["seq"]


def init_chat_mongo() -> None:
    """Create indexes and seed the message counter.

    Schemaless — no PRAGMA/ALTER migration ladder. Safe to call repeatedly.
    """
    _log_connection()
    sessions.create_index(
        [("user_id", ASCENDING), ("updated_at", DESCENDING), ("created_at", DESCENDING)]
    )
    sessions.create_index([("user_id", ASCENDING), ("created_at", DESCENDING)])
    messages.create_index([("session_id", ASCENDING), ("_id", ASCENDING)])
    messages.create_index(
        [("session_id", ASCENDING), ("role", ASCENDING), ("_id", ASCENDING)]
    )
    # One text index per collection, over the three content columns, for the
    # cross-session retrieval candidate fetch (lexical_search).
    messages.create_index([("content", TEXT), ("content_en", TEXT), ("content_es", TEXT)])
    counters.update_one({"_id": "messages"}, {"$setOnInsert": {"seq": 0}}, upsert=True)
