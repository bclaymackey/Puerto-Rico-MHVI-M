"""Account operations: change password, security question, security-answer reset.

Runs against the isolated test database (mongo_test_db fixture).
"""

import pytest

from auth.core import (
    change_password,
    login,
    set_security_question,
    reset_password_with_answer,
    signup,
    verify_password,
)
from auth.db import get_users
from bson import ObjectId

pytestmark = pytest.mark.usefixtures("mongo_test_db")


def _make_user(email="tom@example.com", pw="secret@1"):
    user, err = signup(email, pw)
    assert err is None
    return user["userId"]


# ── change_password ──────────────────────────────────────────────────────────
def test_change_password_succeeds_with_correct_current():
    uid = _make_user()
    ok, err = change_password(uid, "secret@1", "newpass@2")
    assert ok is True and err is None
    # Old password no longer works; new one does.
    assert login("tom@example.com", "secret@1")[1] is not None
    assert login("tom@example.com", "newpass@2")[1] is None


def test_change_password_rejects_wrong_current():
    uid = _make_user()
    ok, err = change_password(uid, "wrong@9", "newpass@2")
    assert ok is False
    assert "current password" in err.lower()


def test_change_password_enforces_new_password_rules():
    uid = _make_user()
    ok, err = change_password(uid, "secret@1", "weak")
    assert ok is False
    assert "at least 8" in err


def test_change_password_stores_a_new_hash():
    uid = _make_user()
    before = get_users().find_one({"_id": ObjectId(uid)})["password_hash"]
    change_password(uid, "secret@1", "newpass@2")
    after = get_users().find_one({"_id": ObjectId(uid)})["password_hash"]
    assert before != after
    assert verify_password("newpass@2", after) is True


# ── set_security_question ────────────────────────────────────────────────────
def test_set_security_question_stores_question_and_hashed_answer():
    uid = _make_user()
    ok, err = set_security_question(uid, "First pet?", "Rex")
    assert ok is True and err is None
    doc = get_users().find_one({"_id": ObjectId(uid)})
    assert doc["security_question"] == "First pet?"
    assert doc["security_answer_hash"] and doc["security_answer_hash"] != "Rex"


def test_set_security_question_rejects_empty():
    uid = _make_user()
    ok, err = set_security_question(uid, "", "Rex")
    assert ok is False
    ok2, err2 = set_security_question(uid, "First pet?", "")
    assert ok2 is False


# ── reset_password_with_answer ───────────────────────────────────────────────
def test_reset_with_correct_answer_sets_new_password():
    uid = _make_user()
    set_security_question(uid, "First pet?", "Rex")
    ok, err = reset_password_with_answer("tom@example.com", "rex", "brandnew@3")  # case-insensitive
    assert ok is True and err is None
    assert login("tom@example.com", "brandnew@3")[1] is None
    assert login("tom@example.com", "secret@1")[1] is not None  # old pw dead


def test_reset_with_wrong_answer_fails():
    uid = _make_user()
    set_security_question(uid, "First pet?", "Rex")
    ok, err = reset_password_with_answer("tom@example.com", "wrong", "brandnew@3")
    assert ok is False
    assert "answer" in err.lower()
    assert login("tom@example.com", "secret@1")[1] is None  # unchanged


def test_reset_without_security_question_set_fails():
    _make_user("nq@example.com", "secret@1")
    ok, err = reset_password_with_answer("nq@example.com", "anything", "brandnew@3")
    assert ok is False
    assert "no security question" in err.lower()


def test_reset_enforces_new_password_rules():
    uid = _make_user()
    set_security_question(uid, "First pet?", "Rex")
    ok, err = reset_password_with_answer("tom@example.com", "Rex", "weak")
    assert ok is False
    assert "at least 8" in err
