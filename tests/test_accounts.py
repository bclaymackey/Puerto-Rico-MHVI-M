"""Account operations: signup, login, get_public_user (auth.core).

Runs against the isolated test database provided by the `mongo_test_db` fixture.
"""

import pytest

from auth.core import get_public_user, login, signup, verify_password
from auth.db import get_users

pytestmark = pytest.mark.usefixtures("mongo_test_db")


# ── signup ──────────────────────────────────────────────────────────────────
def test_signup_creates_user_and_returns_public_fields():
    user, err = signup("Tom@Example.com", "secret@1")
    assert err is None
    assert user["email"] == "tom@example.com"       # normalized
    assert user["name"] is None
    assert "userId" in user and user["userId"]
    assert "password_hash" not in user              # never leak the hash


def test_signup_stores_bcrypt_hash_not_plaintext():
    signup("tom@example.com", "secret@1")
    stored = get_users().find_one({"email": "tom@example.com"})
    assert stored["password_hash"] != "secret@1"
    assert verify_password("secret@1", stored["password_hash"]) is True
    assert stored["role"] == "user"
    assert stored["name_prompted"] is False


def test_signup_rejects_duplicate_email():
    signup("tom@example.com", "secret@1")
    user, err = signup("TOM@example.com", "other@9")   # same email, different case
    assert user is None
    assert "already exists" in err


def test_signup_rejects_invalid_email():
    user, err = signup("not-an-email", "secret@1")
    assert user is None
    assert "valid email" in err


def test_signup_rejects_weak_password():
    user, err = signup("tom@example.com", "short")
    assert user is None
    assert "at least 8" in err


# ── login ───────────────────────────────────────────────────────────────────
def test_login_succeeds_with_correct_credentials():
    signup("tom@example.com", "secret@1")
    user, err = login("Tom@Example.com", "secret@1")
    assert err is None
    assert user["email"] == "tom@example.com"
    assert user["userId"]


def test_login_fails_with_wrong_password():
    signup("tom@example.com", "secret@1")
    user, err = login("tom@example.com", "wrong@9")
    assert user is None
    assert err == "Invalid email or password."


def test_login_fails_for_unknown_email():
    user, err = login("nobody@example.com", "secret@1")
    assert user is None
    assert err == "Invalid email or password."     # same message → no account enumeration


# ── get_public_user (/me) ───────────────────────────────────────────────────
def test_get_public_user_returns_safe_fields():
    created, _ = signup("tom@example.com", "secret@1")
    me = get_public_user(created["userId"])
    assert me == {"userId": created["userId"], "email": "tom@example.com", "name": None}


def test_get_public_user_none_for_missing():
    assert get_public_user(None) is None
    assert get_public_user("64" + "0" * 22) is None    # well-formed but nonexistent id
