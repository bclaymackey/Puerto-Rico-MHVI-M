"""Entity carry-over for multi-turn data queries.

When a follow-up like "of both", "sure", or "yes" names no municipality or
category, resolve the *active* entities from the most recent prior turn in the
same session that did name them. Only ever carries forward what the user already
mentioned — it never invents or adds extra municipalities.
"""

import pandas as pd

from data import get_db_connection

from mongodb import chat_dal
from .data_context_builder import (
    _is_comparison_query,
    _is_overall_query,
    detect_category,
    find_all_municipalities,
)
from .hyperparameters import CARRY_OVER_SCAN_LIMIT as _CARRY_OVER_SCAN_LIMIT

_BREAKDOWN_KEYWORDS = [
    # English
    "breakdown", "break down", "full breakdown", "all categories",
    "all domains", "all the categories", "all the domains", "each category",
    "each domain", "every category", "every domain", "detailed", "in detail",
    "category by category", "domain by domain", "full comparison",
    # Spanish
    "desglose", "desglosado", "todas las categorías", "todas las categorias",
    "todos los dominios", "cada categoría", "cada categoria", "detallado",
    "en detalle", "comparación completa", "comparacion completa",
]


def _wants_breakdown(text_lower: str) -> bool:
    return any(kw in text_lower for kw in _BREAKDOWN_KEYWORDS)


def _recent_session_messages(session_id: str) -> list[str]:
    """Return recent message contents for this session, newest first."""
    return chat_dal.recent_session_message_contents(session_id, _CARRY_OVER_SCAN_LIMIT)


def resolve_active_entities(session_id: str, user_input: str) -> dict:
    """Resolve the municipalities/category in play for this turn.

    Returns {"municipalities": [{"name","fips_code"}], "category": (table, display)|(None,None),
             "wants_overall": bool, "wants_breakdown": bool}.

    Municipalities/category are taken from the current message first; if absent,
    they fall back to the most recent prior message of this session that named
    them. Intent flags (overall / breakdown) are read from the current message.
    """
    text_lower = (user_input or "").lower()

    conn = get_db_connection()
    try:
        muni_df = pd.read_sql("SELECT name, fips_code FROM municipalities", conn)
    finally:
        conn.close()

    # Current message first.
    municipalities = find_all_municipalities(text_lower, muni_df)

    cat_search = text_lower
    for m in municipalities:
        cat_search = cat_search.replace(m["name"].lower(), " ")
    category = detect_category(cat_search)

    # Carry municipalities back from the most recent prior turn that named any.
    if not municipalities:
        for content in _recent_session_messages(session_id):
            prior = find_all_municipalities(content.lower(), muni_df)
            if prior:
                municipalities = prior
                break

    # Carry category back similarly if still unknown.
    if category == (None, None):
        for content in _recent_session_messages(session_id):
            prior_lower = content.lower()
            prior_cat = detect_category(prior_lower)
            if prior_cat != (None, None):
                category = prior_cat
                break

    return {
        "municipalities": municipalities,
        "category": category,
        "wants_overall": _is_overall_query(text_lower) or _is_comparison_query(text_lower),
        "wants_breakdown": _wants_breakdown(text_lower),
    }
