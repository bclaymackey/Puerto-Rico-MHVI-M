"""One-off migration: re-key all anonymous chat history onto a single admin account.

Anonymous users are the pre-login browser-UUID identities — their `users` docs have
no real email (`email` is null or absent). Their chat lives in `sessions` (keyed by
`user_id`) and `messages` (keyed by `session_id`). Re-keying the sessions' `user_id`
to the admin moves everything; messages need no change because they reference the
session, not the user.

The logic here is pure and testable; `mongodb/migrate_auth.py` is the CLI wrapper.
"""

from datetime import datetime, timezone

from bson import ObjectId

from auth.core import hash_password, normalize_email
from auth.db import get_users


# Anonymous = email is null OR the field is absent.
_ANON_FILTER = {"$or": [{"email": None}, {"email": {"$exists": False}}]}


def ensure_admin(email: str, password: str) -> str:
    """Create the admin account if absent; return its id (str). Idempotent."""
    email = normalize_email(email)
    existing = get_users().find_one({"email": email})
    if existing:
        return str(existing["_id"])
    result = get_users().insert_one(
        {
            "email": email,
            "password_hash": hash_password(password),
            "name": "Admin",
            "role": "admin",
            "name_prompted": True,          # admin is never asked its name in chat
            "security_question": None,
            "security_answer_hash": None,
            "reset_token": None,
            "reset_expires": None,
            "created_at": datetime.now(timezone.utc),
        }
    )
    return str(result.inserted_id)


def _anon_user_ids() -> list:
    return [u["_id"] for u in get_users().find(_ANON_FILTER, {"_id": 1})]


def rekey_anonymous_to_admin(admin_id: str, dry_run: bool = True) -> dict:
    """Move every anonymous user's sessions to the admin and delete the anon users.

    Returns counts. With dry_run=True nothing is written.
    """
    # Resolve sessions through the same database auth is pointed at, so tests and
    # production both operate on the right db (sessions live in the chat client).
    db = get_users().database
    sessions_coll = db.sessions

    anon_ids = _anon_user_ids()
    # Exclude the admin itself, just in case its email hasn't been set yet.
    admin_oid = ObjectId(admin_id)
    anon_ids = [uid for uid in anon_ids if uid != admin_oid]

    sessions_to_move = sessions_coll.count_documents({"user_id": {"$in": anon_ids}})

    result = {
        "admin_id": admin_id,
        "anon_users": len(anon_ids),
        "sessions_rekeyed": sessions_to_move,
        "applied": not dry_run,
    }
    if dry_run:
        return result

    if anon_ids:
        sessions_coll.update_many(
            {"user_id": {"$in": anon_ids}}, {"$set": {"user_id": admin_id}}
        )
        get_users().delete_many({"_id": {"$in": anon_ids}})
    return result
