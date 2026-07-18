"""Self-hosted email+password auth: password rules, bcrypt hashing, and
server-side cookie sessions stored in MongoDB.

Pure logic + Mongo (no Flask/Dash imports) so it is unit-testable in isolation.
Collection access goes through `auth.db` so tests can use an isolated database.
"""

import hashlib
import os
import re
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
from bson import ObjectId
from bson.errors import InvalidId

from auth.db import get_auth_sessions, get_users

_SPECIAL = set("!@#$%^&*()-_=+[]{};:,.<>?/\\|`~")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

_SESSION_DAYS_SHORT = 1     # no "remember me"
_SESSION_DAYS_LONG = 30     # "remember me"


# ── password rules ──────────────────────────────────────────────────────────
def validate_password(pw: str) -> str | None:
    """Return an error message, or None if the password is acceptable.

    Rules: at least 8 characters, at least one special character, and within
    bcrypt's 72-byte limit.
    """
    if len(pw) < 8:
        return "Password must be at least 8 characters."
    if not any(c in _SPECIAL for c in pw):
        return "Password must contain at least one special character (e.g. @)."
    if len(pw.encode("utf-8")) > 72:
        return "Password is too long."
    return None


# ── password hashing (bcrypt) ───────────────────────────────────────────────
def hash_password(pw: str) -> str:
    """bcrypt hash, returned as a str for storage. bcrypt operates on bytes."""
    return bcrypt.hashpw(pw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(pw: str, hashed: str) -> bool:
    """Constant-time check. Returns False (not raises) on a malformed hash."""
    try:
        return bcrypt.checkpw(pw.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# ── email helpers ───────────────────────────────────────────────────────────
def normalize_email(email: str | None) -> str:
    return (email or "").strip().lower()


def valid_email(email: str | None) -> bool:
    return bool(_EMAIL_RE.match(email or ""))


# ── server-side cookie sessions ─────────────────────────────────────────────
def _hash_token(raw: str) -> str:
    """Peppered SHA-256 of the raw cookie token. Only the hash is persisted, so a
    leaked database can't be used to forge cookies without the server pepper."""
    pepper = os.getenv("AUTH_TOKEN_PEPPER", "")
    return hashlib.sha256((raw + pepper).encode("utf-8")).hexdigest()


def create_session(user_id: str, remember: bool) -> str:
    """Insert a session row and return the RAW token to put in the cookie."""
    raw = secrets.token_urlsafe(32)
    days = _SESSION_DAYS_LONG if remember else _SESSION_DAYS_SHORT
    now = datetime.now(timezone.utc)
    get_auth_sessions().insert_one(
        {
            "token_hash": _hash_token(raw),
            "user_id": user_id,
            "created_at": now,
            "expires_at": now + timedelta(days=days),
            "remember": remember,
        }
    )
    return raw


def resolve_session(raw_token: str | None) -> str | None:
    """Cookie token -> user_id, or None if missing/unknown/expired.

    The TTL index removes expired rows eventually; we also guard on expires_at in
    case the background sweep hasn't run yet.
    """
    if not raw_token:
        return None
    row = get_auth_sessions().find_one({"token_hash": _hash_token(raw_token)})
    if not row:
        return None
    expires_at = row["expires_at"]
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)  # Mongo returns naive UTC
    if expires_at <= datetime.now(timezone.utc):
        return None
    return row["user_id"]


def revoke_session(raw_token: str | None) -> None:
    if raw_token:
        get_auth_sessions().delete_one({"token_hash": _hash_token(raw_token)})


# ── account operations: signup / login / me ─────────────────────────────────
def signup(email: str, password: str) -> tuple[dict | None, str | None]:
    """Create an account. Returns (public_user, None) or (None, error_message)."""
    email = normalize_email(email)
    if not valid_email(email):
        return None, "Please enter a valid email address."
    # Existence is checked before password strength: if the email is already
    # taken, that's the error the user needs, regardless of the password entered.
    if get_users().find_one({"email": email}):
        return None, "An account with this email already exists."
    pw_err = validate_password(password)
    if pw_err:
        return None, pw_err

    result = get_users().insert_one(
        {
            "email": email,
            "password_hash": hash_password(password),
            "name": None,
            "role": "user",
            "name_prompted": False,
            "security_question": None,
            "security_answer_hash": None,
            "reset_token": None,
            "reset_expires": None,
            "created_at": datetime.now(timezone.utc),
        }
    )
    return {"userId": str(result.inserted_id), "email": email, "name": None}, None


def login(email: str, password: str) -> tuple[dict | None, str | None]:
    email = normalize_email(email)
    user = get_users().find_one({"email": email})
    # Same message whether the email is unknown or the password is wrong, so the
    # response can't be used to enumerate which emails have accounts.
    if not user or not verify_password(password, user.get("password_hash", "")):
        return None, "Invalid email or password."
    return {"userId": str(user["_id"]), "email": user["email"], "name": user.get("name")}, None


def get_public_user(user_id: str | None) -> dict | None:
    """Safe user payload for /auth/me — never includes password/security hashes."""
    if not user_id:
        return None
    try:
        oid = ObjectId(user_id)
    except (InvalidId, TypeError):
        return None
    user = get_users().find_one(
        {"_id": oid}, {"password_hash": 0, "security_answer_hash": 0}
    )
    if not user:
        return None
    return {"userId": str(user["_id"]), "email": user.get("email"), "name": user.get("name")}


def _normalize_answer(answer: str) -> str:
    """Security answers match case- and whitespace-insensitively."""
    return " ".join((answer or "").strip().lower().split())


# ── account management: change password / security question / reset ──────────
def change_password(user_id: str, current: str, new: str) -> tuple[bool, str | None]:
    """Change a logged-in user's password after verifying the current one."""
    try:
        oid = ObjectId(user_id)
    except (InvalidId, TypeError):
        return False, "Invalid account."
    user = get_users().find_one({"_id": oid})
    if not user or not verify_password(current, user.get("password_hash", "")):
        return False, "Your current password is incorrect."
    pw_err = validate_password(new)
    if pw_err:
        return False, pw_err
    get_users().update_one({"_id": oid}, {"$set": {"password_hash": hash_password(new)}})
    return True, None


def set_security_question(user_id: str, question: str, answer: str) -> tuple[bool, str | None]:
    """Store an optional security question + hashed answer for self-service reset."""
    try:
        oid = ObjectId(user_id)
    except (InvalidId, TypeError):
        return False, "Invalid account."
    question = (question or "").strip()
    if not question:
        return False, "Please enter a security question."
    if not _normalize_answer(answer):
        return False, "Please enter an answer."
    get_users().update_one(
        {"_id": oid},
        {
            "$set": {
                "security_question": question,
                "security_answer_hash": hash_password(_normalize_answer(answer)),
            }
        },
    )
    return True, None


def get_security_question(email: str) -> str | None:
    """The security question for an email, or None if none set / no such user."""
    user = get_users().find_one({"email": normalize_email(email)})
    return user.get("security_question") if user else None


def reset_password_with_answer(
    email: str, answer: str, new_password: str
) -> tuple[bool, str | None]:
    """Self-service reset: verify the security answer, then set a new password."""
    user = get_users().find_one({"email": normalize_email(email)})
    if not user or not user.get("security_answer_hash"):
        return False, "No security question is set for this account."
    if not verify_password(_normalize_answer(answer), user["security_answer_hash"]):
        return False, "That answer is incorrect."
    pw_err = validate_password(new_password)
    if pw_err:
        return False, pw_err
    get_users().update_one(
        {"_id": user["_id"]}, {"$set": {"password_hash": hash_password(new_password)}}
    )
    return True, None
