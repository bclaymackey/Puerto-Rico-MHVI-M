"""The existing chat-DB startup path also provisions the auth indexes.

Verifies that init_chat_mongo() creates the auth_sessions TTL + token indexes and
the unique email index, so a normal app boot leaves auth ready. Runs against the
isolated test database (auth.db is pointed at it by the mongo_test_db fixture),
and temporarily points mongodb.client at the same database.
"""

import pytest

pytestmark = pytest.mark.usefixtures("mongo_test_db")


def test_init_chat_mongo_creates_auth_indexes(mongo_test_db, monkeypatch):
    import mongodb.client as client_mod

    # Drop the auth indexes the session fixture created, so this test genuinely
    # proves init_chat_mongo() re-creates them rather than finding them present.
    mongo_test_db.auth_sessions.drop_indexes()
    mongo_test_db.users.drop_indexes()
    assert not any(
        ix.get("expireAfterSeconds") is not None
        for ix in mongo_test_db.auth_sessions.index_information().values()
    ), "TTL index should be gone before init_chat_mongo() runs"

    # Point the chat client module at the isolated test database for this test.
    monkeypatch.setattr(client_mod, "db", mongo_test_db)
    monkeypatch.setattr(client_mod, "users", mongo_test_db.users)
    monkeypatch.setattr(client_mod, "sessions", mongo_test_db.sessions)
    monkeypatch.setattr(client_mod, "messages", mongo_test_db.messages)
    monkeypatch.setattr(client_mod, "counters", mongo_test_db.counters)

    client_mod.init_chat_mongo()

    session_indexes = mongo_test_db.auth_sessions.index_information()
    user_indexes = mongo_test_db.users.index_information()

    # A TTL index exists on the auth_sessions.expires_at field.
    ttl = [ix for ix in session_indexes.values() if ix.get("expireAfterSeconds") is not None]
    assert ttl, "expected a TTL index on auth_sessions"
    assert any(key[0][0] == "expires_at" for key in [ix["key"] for ix in ttl])

    # token_hash is uniquely indexed for fast lookup.
    assert any(
        ix["key"][0][0] == "token_hash" and ix.get("unique")
        for ix in session_indexes.values()
    )

    # email is uniquely indexed on users.
    assert any(
        ix["key"][0][0] == "email" and ix.get("unique")
        for ix in user_indexes.values()
    )
