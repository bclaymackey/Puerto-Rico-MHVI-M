"""Unit tests for tickets.core — validate_ticket, create_ticket, list_tickets.

All tests run against the isolated throwaway MongoDB set up by conftest.py
(mongo_test_db fixture). No browser or Dash required.
"""

from tickets.core import (
    MESSAGE_MAX,
    SUBJECT_MAX,
    create_ticket,
    list_tickets,
    validate_ticket,
)
from tickets.db import get_tickets


# ── validate_ticket ──────────────────────────────────────────────────────────

def test_validate_ticket_accepts_well_formed(mongo_test_db):
    assert validate_ticket("Technical", "Map fails to load", "Long description here.") is None


def test_validate_ticket_rejects_empty_subject(mongo_test_db):
    err = validate_ticket("Technical", "", "Some message")
    assert err is not None
    assert "subject" in err.lower()


def test_validate_ticket_rejects_whitespace_subject(mongo_test_db):
    err = validate_ticket("Data", "   ", "Some message")
    assert err is not None


def test_validate_ticket_rejects_empty_message(mongo_test_db):
    err = validate_ticket("Account", "Valid subject", "")
    assert err is not None
    assert "message" in err.lower()


def test_validate_ticket_rejects_whitespace_message(mongo_test_db):
    err = validate_ticket("Other", "Valid subject", "   ")
    assert err is not None


def test_validate_ticket_rejects_unknown_category(mongo_test_db):
    err = validate_ticket("Billing", "subject", "message")
    assert err is not None
    assert "category" in err.lower()


def test_validate_ticket_rejects_none_category(mongo_test_db):
    err = validate_ticket(None, "subject", "message")
    assert err is not None


def test_validate_ticket_rejects_over_length_subject(mongo_test_db):
    err = validate_ticket("Technical", "x" * (SUBJECT_MAX + 1), "message")
    assert err is not None
    assert str(SUBJECT_MAX) in err


def test_validate_ticket_rejects_over_length_message(mongo_test_db):
    err = validate_ticket("Technical", "subject", "x" * (MESSAGE_MAX + 1))
    assert err is not None
    assert str(MESSAGE_MAX) in err


def test_validate_ticket_accepts_exact_max_lengths(mongo_test_db):
    assert validate_ticket("Other", "x" * SUBJECT_MAX, "x" * MESSAGE_MAX) is None


# ── create_ticket ────────────────────────────────────────────────────────────

def test_create_ticket_no_user_id(mongo_test_db):
    ticket, err = create_ticket(None, "a@b.com", "Technical", "subj", "msg")
    assert ticket is None
    assert err is not None


def test_create_ticket_empty_user_id(mongo_test_db):
    ticket, err = create_ticket("", "a@b.com", "Technical", "subj", "msg")
    assert ticket is None
    assert err is not None


def test_create_ticket_invalid_fields_propagate_validation(mongo_test_db):
    ticket, err = create_ticket("user-1", "a@b.com", "Technical", "", "msg")
    assert ticket is None
    assert err is not None


def test_create_ticket_happy_path(mongo_test_db):
    ticket, err = create_ticket(
        "user-happy", "happy@example.com", "Data", "Test subject", "Test message body."
    )
    assert err is None
    assert ticket is not None
    assert isinstance(ticket["_id"], str)
    assert ticket["status"] == "open"
    assert ticket["created_at"] is not None

    # Confirm the document is actually in the collection.
    stored = get_tickets().find_one({"user_id": "user-happy"})
    assert stored is not None
    assert stored["status"] == "open"
    assert stored["category"] == "Data"


# ── list_tickets ─────────────────────────────────────────────────────────────

def test_list_tickets_returns_only_given_users_tickets(mongo_test_db):
    create_ticket("user-a", "a@x.com", "Technical", "subj-a1", "msg")
    create_ticket("user-a", "a@x.com", "Other", "subj-a2", "msg")
    create_ticket("user-b", "b@x.com", "Account", "subj-b1", "msg")

    result = list_tickets("user-a")
    assert len(result) == 2
    subjects = {t["subject"] for t in result}
    assert subjects == {"subj-a1", "subj-a2"}


def test_list_tickets_newest_first(mongo_test_db):
    from datetime import datetime, timezone, timedelta
    from tickets.db import get_tickets

    # Insert directly with explicit timestamps so ordering is deterministic.
    now = datetime.now(timezone.utc)
    get_tickets().insert_one({
        "user_id": "user-ord", "email": "o@x.com", "category": "Technical",
        "subject": "first", "message": "msg", "status": "open",
        "created_at": now,
    })
    get_tickets().insert_one({
        "user_id": "user-ord", "email": "o@x.com", "category": "Technical",
        "subject": "second", "message": "msg", "status": "open",
        "created_at": now + timedelta(seconds=1),
    })

    result = list_tickets("user-ord")
    assert result[0]["subject"] == "second"
    assert result[1]["subject"] == "first"


def test_list_tickets_no_user_returns_empty(mongo_test_db):
    assert list_tickets(None) == []
    assert list_tickets("") == []
