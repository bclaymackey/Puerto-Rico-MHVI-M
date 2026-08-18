"""Support ticket logic — pure, framework-agnostic.

Collection access goes through `tickets.db` so tests can use an isolated
database. This is the single seam for a future email step: add one guarded
line `_notify(ticket)` after a successful insert — no caller changes required.
"""

from datetime import datetime, timezone

from tickets.db import get_tickets

CATEGORIES = ("Technical", "Account", "Data", "Other")
SUBJECT_MAX = 120
MESSAGE_MAX = 2000


def validate_ticket(
    category: str | None,
    subject: str | None,
    message: str | None,
) -> str | None:
    """Return an error string, or None if the ticket fields are valid.

    All fields are stripped before checking; None is treated as empty.
    """
    category = (category or "").strip()
    subject = (subject or "").strip()
    message = (message or "").strip()

    if category not in CATEGORIES:
        return f"Category must be one of: {', '.join(CATEGORIES)}."
    if not subject:
        return "Subject is required."
    if len(subject) > SUBJECT_MAX:
        return f"Subject must be {SUBJECT_MAX} characters or fewer."
    if not message:
        return "Message is required."
    if len(message) > MESSAGE_MAX:
        return f"Message must be {MESSAGE_MAX} characters or fewer."
    return None


def create_ticket(
    user_id: str | None,
    email: str | None,
    category: str | None,
    subject: str | None,
    message: str | None,
) -> tuple[dict | None, str | None]:
    """Validate and persist a new support ticket.

    Returns (ticket_dict, None) on success or (None, error_string) on failure.
    The returned dict has _id stringified so callers never see an ObjectId.
    """
    if not user_id:
        return None, "You must be logged in to submit a ticket."

    err = validate_ticket(category, subject, message)
    if err:
        return None, err

    doc = {
        "user_id": user_id,
        "email": (email or "").strip(),
        "category": category.strip(),
        "subject": subject.strip(),
        "message": message.strip(),
        "status": "open",
        "created_at": datetime.now(timezone.utc),
    }
    result = get_tickets().insert_one(doc)
    doc["_id"] = str(result.inserted_id)
    return doc, None


def list_tickets(user_id: str | None, limit: int = 20) -> list[dict]:
    """Return the most recent tickets for a user, newest first."""
    if not user_id:
        return []
    cursor = (
        get_tickets()
        .find({"user_id": user_id})
        .sort("created_at", -1)
        .limit(limit)
    )
    result = []
    for doc in cursor:
        doc["_id"] = str(doc["_id"])
        result.append(doc)
    return result
