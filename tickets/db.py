"""Tickets collection handle — the single indirection point for the database.

`core.py` never imports bound collection objects directly; it calls the accessor
here. That lets tests point tickets at an isolated throwaway database (via
`use_database`) without touching the real chat DB, and keeps all ticket-collection
wiring in one place for easy navigation and rollback.
"""

from pymongo import ASCENDING, DESCENDING

from mongodb.client import db as _default_db

_db = _default_db


def use_database(database) -> None:
    """Point tickets at a specific pymongo Database (used by tests for isolation)."""
    global _db
    _db = database


def get_tickets():
    return _db.tickets


def ensure_ticket_indexes() -> None:
    """Index on (user_id ASC, created_at DESC) for fast per-user ticket listing.

    Idempotent — safe to call repeatedly.
    """
    get_tickets().create_index(
        [("user_id", ASCENDING), ("created_at", DESCENDING)]
    )
