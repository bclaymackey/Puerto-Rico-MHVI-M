"""Anonymous → admin re-key migration (auth.migrate).

Simulates the real DB shape (anonymous users with email=None owning sessions that
own messages) in the isolated test database, then verifies the re-key moves all
anonymous history under a single admin account without losing messages.
"""

import pytest

from auth.migrate import ensure_admin, rekey_anonymous_to_admin
from auth.db import get_users

pytestmark = pytest.mark.usefixtures("mongo_test_db")


def _seed_anonymous(db, n_users=3, sessions_per_user=2, msgs_per_session=2):
    """Create anonymous users (email=None) with sessions and messages, like pr_chat."""
    for u in range(n_users):
        uid = f"anon-{u}"
        db.users.insert_one({"_id": uid, "email": None, "name": None})
        for s in range(sessions_per_user):
            sid = f"sess-{u}-{s}"
            db.sessions.insert_one({"_id": sid, "user_id": uid})
            for _ in range(msgs_per_session):
                db.messages.insert_one({"session_id": sid, "role": "user", "content": "hi"})


# ── admin creation ──────────────────────────────────────────────────────────
def test_ensure_admin_creates_admin_user():
    admin_id = ensure_admin("admin@site.org", "admin@123")
    doc = get_users().find_one({"_id": __import__("bson").ObjectId(admin_id)})
    assert doc["email"] == "admin@site.org"
    assert doc["role"] == "admin"
    assert doc["name_prompted"] is True          # admin isn't asked its name in chat


def test_ensure_admin_is_idempotent():
    first = ensure_admin("admin@site.org", "admin@123")
    second = ensure_admin("admin@site.org", "admin@123")
    assert first == second
    assert get_users().count_documents({"email": "admin@site.org"}) == 1


# ── re-key ──────────────────────────────────────────────────────────────────
def test_dry_run_reports_counts_without_writing(mongo_test_db):
    _seed_anonymous(mongo_test_db)  # 3 users, 6 sessions, 12 messages
    admin_id = ensure_admin("admin@site.org", "admin@123")

    result = rekey_anonymous_to_admin(admin_id, dry_run=True)

    assert result["anon_users"] == 3
    assert result["sessions_rekeyed"] == 6
    # Nothing changed on disk.
    assert mongo_test_db.sessions.count_documents({"user_id": admin_id}) == 0
    assert mongo_test_db.users.count_documents({"email": None}) == 3


def test_apply_rekeys_sessions_and_removes_anon_users(mongo_test_db):
    _seed_anonymous(mongo_test_db)
    admin_id = ensure_admin("admin@site.org", "admin@123")

    result = rekey_anonymous_to_admin(admin_id, dry_run=False)

    assert result["sessions_rekeyed"] == 6
    assert mongo_test_db.sessions.count_documents({"user_id": admin_id}) == 6
    assert mongo_test_db.sessions.count_documents({"user_id": {"$regex": "^anon-"}}) == 0
    assert mongo_test_db.users.count_documents({"email": None}) == 0
    # Messages are untouched and still reachable via their sessions.
    assert mongo_test_db.messages.count_documents({}) == 12


def test_apply_does_not_touch_the_admins_own_data(mongo_test_db):
    _seed_anonymous(mongo_test_db)
    admin_id = ensure_admin("admin@site.org", "admin@123")
    # Admin already owns a session (e.g. from prior login) — must survive.
    mongo_test_db.sessions.insert_one({"_id": "admin-sess", "user_id": admin_id})

    rekey_anonymous_to_admin(admin_id, dry_run=False)

    assert mongo_test_db.sessions.find_one({"_id": "admin-sess"})["user_id"] == admin_id
    assert get_users().find_one({"_id": __import__("bson").ObjectId(admin_id)}) is not None


def test_apply_is_idempotent(mongo_test_db):
    _seed_anonymous(mongo_test_db)
    admin_id = ensure_admin("admin@site.org", "admin@123")

    rekey_anonymous_to_admin(admin_id, dry_run=False)
    second = rekey_anonymous_to_admin(admin_id, dry_run=False)   # nothing left to move

    assert second["anon_users"] == 0
    assert second["sessions_rekeyed"] == 0
    assert mongo_test_db.sessions.count_documents({"user_id": admin_id}) == 6
