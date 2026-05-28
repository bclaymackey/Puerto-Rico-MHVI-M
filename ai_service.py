import re
import uuid
from datetime import datetime

import pandas as pd

from chat_history_manager import build_llm_context, save_ai_response
from data import get_db_connection
from data_context_builder import find_all_municipalities, get_data_context
from llm_caller import call_llm
from navigation_guide import build_navigation_response, is_navigation_intent
from report_data_builder import get_report_data
from report_generator import generate_report_text
from report_pdf import build_report_pdf


_REPORT_KEYWORDS_EN = [
    "pdf",
    "report",
    "printable report",
    "municipality report",
    "full report",
    "vulnerability report",
    "download report",
    "generate a report",
    "create a report",
    "make a report",
]
_REPORT_KEYWORDS_ES = [
    "pdf",
    "informe",
    "reporte",
    "informe municipal",
    "informe completo",
    "informe de vulnerabilidad",
    "descargar informe",
    "genera un informe",
    "generar un informe",
    "crear un informe",
    "haz un informe",
]


# Server-side, single-process cache. Single-use: consume_report pops.
# Acceptable for single-worker Dash dev; for multi-worker prod, swap for Redis.
_REPORT_CACHE: dict = {}


def _is_report_intent(text_lower: str, language: str) -> bool:
    keywords = _REPORT_KEYWORDS_ES if language == "es" else _REPORT_KEYWORDS_EN
    # Always also accept the universal English "pdf"/"report" triggers.
    extras = ["pdf", "report"]
    for kw in keywords + extras:
        if re.search(rf"\b{re.escape(kw)}\b", text_lower):
            return True
    return False


def _ack_message(municipality: str, language: str) -> str:
    if language == "es":
        return f"Tu informe de {municipality} está listo."
    return f"Your {municipality} report is ready."


def _need_municipality_message(language: str) -> str:
    if language == "es":
        return (
            "Por favor especifica un municipio para el informe. "
            "Ejemplo: \"Genera un informe para Arecibo\"."
        )
    return (
        "Please specify a municipality for the report. "
        "Example: \"Generate a report for Arecibo\"."
    )


def _no_data_message(municipality: str, language: str) -> str:
    if language == "es":
        return f"No se encontraron datos suficientes para generar un informe de {municipality}."
    return f"Not enough data was found to generate a report for {municipality}."


def _safe_filename_stem(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "_", name).strip("_").lower()
    return cleaned or "municipality"


def _generate_report_response(user_input: str, language: str, session_id: str) -> dict:
    """Detect municipality, build report, cache PDF, return report dict."""
    conn = get_db_connection()
    try:
        muni_df = pd.read_sql("SELECT name, fips_code FROM municipalities", conn)
    finally:
        conn.close()

    found = find_all_municipalities(user_input.lower(), muni_df)
    if not found:
        msg = _need_municipality_message(language)
        save_ai_response(session_id, msg)
        return {"kind": "text", "text": msg}

    # v1: single municipality only — take the first mention if multiple.
    municipality = found[0]["name"]
    report_data = get_report_data(municipality)
    if not report_data or not report_data.get("categories"):
        msg = _no_data_message(municipality, language)
        save_ai_response(session_id, msg)
        return {"kind": "text", "text": msg}

    try:
        report_text = generate_report_text(report_data, language)
        pdf_bytes = build_report_pdf(report_text, municipality, language)
    except Exception as e:
        print(f"[_generate_report_response] error: {e}")
        msg = _no_data_message(municipality, language)
        save_ai_response(session_id, msg)
        return {"kind": "text", "text": msg}

    token = uuid.uuid4().hex
    timestamp = datetime.now().strftime("%Y-%m-%d")
    filename = f"{_safe_filename_stem(municipality)}_vulnerability_report_{timestamp}.pdf"
    _REPORT_CACHE[token] = (pdf_bytes, filename)

    ack = _ack_message(municipality, language)
    save_ai_response(session_id, ack)
    return {
        "kind": "report",
        "message": ack,
        "report_token": token,
        "filename": filename,
        "municipality": municipality,
    }


def consume_report(token: str):
    """Pop and return (pdf_bytes, filename) for a token, or None if missing."""
    return _REPORT_CACHE.pop(token, None)


def process_chat_message(
    user_input: str,
    language: str = "en",
    session_id: str = "default",
) -> dict:
    """Return a structured response dict.

    Shapes:
        {"kind": "text",   "text": str}
        {"kind": "report", "message": str, "report_token": str, "filename": str, ...}
    """
    text_lower = (user_input or "").lower()

    if _is_report_intent(text_lower, language):
        # Record the user message in history so the report flow shows up there.
        build_llm_context(session_id, user_input)
        return _generate_report_response(user_input, language, session_id)

    if is_navigation_intent(text_lower, language):
        build_llm_context(session_id, user_input)
        steps = build_navigation_response(user_input, language)
        save_ai_response(session_id, steps)
        return {"kind": "text", "text": steps}

    chat_context = build_llm_context(session_id, user_input)
    data_context = get_data_context(user_input, language)
    ai_response = call_llm(chat_context, data_context, language)
    save_ai_response(session_id, ai_response)
    return {"kind": "text", "text": ai_response}
