"""Unit tests for tickets.db — ensure_ticket_indexes() provisioning.

Tests run against the isolated throwaway MongoDB provided by conftest.py.
"""

from pymongo import ASCENDING, DESCENDING

from tickets.db import ensure_ticket_indexes, get_tickets


def test_ensure_ticket_indexes_is_idempotent(mongo_test_db):
    """Calling ensure_ticket_indexes() twice must not raise."""
    ensure_ticket_indexes()
    ensure_ticket_indexes()


def test_ticket_index_exists_after_provisioning(mongo_test_db):
    """The (user_id ASC, created_at DESC) compound index must be present."""
    ensure_ticket_indexes()
    index_info = get_tickets().index_information()
    # Each index is stored under a generated name; inspect their key specs.
    keys_list = [
        tuple(info["key"])
        for info in index_info.values()
    ]
    expected = (("user_id", ASCENDING), ("created_at", DESCENDING))
    assert expected in keys_list, (
        f"Expected index {expected} not found. Indexes present: {keys_list}"
    )
