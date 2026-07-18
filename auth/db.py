"""Auth collection handles — the single indirection point for the database.

`core.py` never imports bound collection objects directly; it calls the accessors
here. That lets tests point auth at an isolated throwaway database (via
`use_database`) without touching the real chat DB, and keeps all auth-collection
wiring in one place for easy navigation and rollback.
"""

from pymongo import ASCENDING

from mongodb.client import db as _default_db

_db = _default_db


def use_database(database) -> None:
    """Point auth at a specific pymongo Database (used by tests for isolation)."""
    global _db
    _db = database


def get_users():
    return _db.users


def get_auth_sessions():
    return _db.auth_sessions


def ensure_auth_indexes() -> None:
    """Unique email, fast token lookup, and a TTL index that auto-expires sessions.

    Idempotent — safe to call repeatedly. The email index is *partial* (only docs
    whose email is a string), so the legacy anonymous users (which carry
    `email: null`) don't collide on null and block the build. `sparse` alone would
    not help here: sparse skips only docs missing the field, but these docs have
    email present and set to null.
    """
    get_users().create_index(
        [("email", ASCENDING)],
        unique=True,
        partialFilterExpression={"email": {"$type": "string"}},
    )
    get_auth_sessions().create_index([("token_hash", ASCENDING)], unique=True)
    get_auth_sessions().create_index("expires_at", expireAfterSeconds=0)
