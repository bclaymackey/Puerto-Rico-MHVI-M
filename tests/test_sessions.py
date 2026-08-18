"""Server-side cookie sessions stored in MongoDB (auth.core).

Runs against the isolated test database provided by the `mongo_test_db` fixture.
"""

from datetime import datetime, timedelta, timezone

import pytest

from auth.core import create_session, resolve_session, revoke_session
from auth.db import get_auth_sessions

pytestmark = pytest.mark.usefixtures("mongo_test_db")


def test_create_returns_token_and_resolves_to_user():
    raw = create_session("user-123", remember=False)
    assert isinstance(raw, str) and raw
    assert resolve_session(raw) == "user-123"


def test_raw_token_is_not_stored_in_plaintext():
    raw = create_session("user-123", remember=False)
    row = get_auth_sessions().find_one({})
    assert row is not None
    assert raw not in str(row)          # only a hash of the token is persisted
    assert row.get("token_hash") and row["token_hash"] != raw


def test_resolve_unknown_token_returns_none():
    assert resolve_session("nonexistent-token") is None


def test_resolve_none_returns_none():
    assert resolve_session(None) is None


def test_revoke_invalidates_session():
    raw = create_session("user-123", remember=False)
    revoke_session(raw)
    assert resolve_session(raw) is None


def test_expired_session_does_not_resolve():
    raw = create_session("user-123", remember=False)
    # Force the stored session into the past.
    get_auth_sessions().update_one(
        {"token_hash": {"$exists": True}},
        {"$set": {"expires_at": datetime.now(timezone.utc) - timedelta(seconds=1)}},
    )
    assert resolve_session(raw) is None


def test_remember_me_extends_expiry():
    create_session("user-a", remember=False)
    create_session("user-b", remember=True)
    rows = {r["user_id"]: r for r in get_auth_sessions().find({})}
    assert rows["user-b"]["expires_at"] > rows["user-a"]["expires_at"]
