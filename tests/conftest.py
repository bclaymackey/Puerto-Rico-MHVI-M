"""Test fixtures for the auth suite.

Every test runs against an isolated throwaway MongoDB database on the local
mongod, so nothing touches the real chat DB (`pr_chat`). The database is created
fresh per test session and dropped afterwards; collections are cleared between
tests for isolation.
"""

import os

import pytest
from pymongo import MongoClient

from auth import db as auth_db


_TEST_DB_NAME = "pr_chat_authtest"


def _point_chat_dal_at(database):
    """Repoint the chat client's collection handles (and chat_dal's bound copies)
    at the given database, so chat_dal and auth share one test DB."""
    import mongodb.client as client_mod
    import mongodb.chat_dal as dal

    for name in ("users", "sessions", "messages", "counters"):
        coll = database[name]
        setattr(client_mod, name, coll)
        if hasattr(dal, name):
            setattr(dal, name, coll)
    client_mod.db = database


@pytest.fixture(scope="session")
def mongo_test_db():
    uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    client = MongoClient(uri)
    database = client[_TEST_DB_NAME]
    client.drop_database(_TEST_DB_NAME)  # clean slate at session start
    auth_db.use_database(database)
    _point_chat_dal_at(database)
    auth_db.ensure_auth_indexes()
    yield database
    client.drop_database(_TEST_DB_NAME)
    client.close()


@pytest.fixture(autouse=True)
def clean_collections(mongo_test_db):
    """Empty all touched collections before each test so tests don't leak."""
    mongo_test_db.users.delete_many({})
    mongo_test_db.auth_sessions.delete_many({})
    mongo_test_db.sessions.delete_many({})
    mongo_test_db.messages.delete_many({})
    yield
