"""Lightweight guided-navigation intent.

Detects "how/where do I…" questions about the dashboard and returns short
numbered UI steps instead of running the data or report flow. Templates only
reference UI that actually exists in layout.py (Category dropdown, the map,
the right side panel, this chat, the Custom Report Builder).

is_custom_report_intent() is checked by ai_service.py BEFORE the generic
report-generation keyword match, since "custom report" would otherwise be
swallowed by the bare "report" keyword and misrouted into the single-
municipality PDF flow. It is deliberately standalone (not gated by
_NAV_PHRASES_EN/ES) so it also matches statements, not just questions.
"""

import pandas as pd

from data import get_db_connection

from .data_context_builder import detect_category, find_all_municipalities


_NAV_PHRASES_EN = [
    "how can i", "how do i", "how would i", "how to ",
    "where can i", "where do i", "where is the",
    "show me where", "show me how",
    "guide me", "walk me through", "navigate to",
]

_NAV_PHRASES_ES = [
    "cómo puedo", "como puedo",
    "cómo encuentro", "como encuentro",
    "cómo veo", "como veo",
    "cómo uso", "como uso",
    "dónde puedo", "donde puedo",
    "dónde encuentro", "donde encuentro",
    "dónde veo", "donde veo",
    "dónde está", "donde esta",
    "muéstrame", "muestrame",
    "guíame", "guiame",
]


# Known-unsupported features. If a navigation question mentions one of these,
# return the "not in this dashboard yet" message instead of generic steps.
_UNSUPPORTED_KEYWORDS = [
    "excel", "csv", "spreadsheet",
    "login", "log in", "sign in", "log out",
    "iniciar sesión", "iniciar sesion", "cerrar sesión", "cerrar sesion",
    "dark mode", "light mode", "modo oscuro", "modo claro",
    "edit data", "modify data", "delete data",
    "editar datos", "modificar datos", "borrar datos",
]

# Support-ticket questions. Matches the real "Report an issue" modal wired to
# tickets/core.py — keep in sync with layout.py's open-ticket-btn / ticket-modal.
_TICKET_KEYWORDS_EN = [
    "ticket", "submit a ticket", "file a ticket", "report an issue",
    "report a bug", "report a problem", "contact support", "get support",
    "help desk", "support request", "file a complaint", "raise an issue",
]
_TICKET_KEYWORDS_ES = [
    "boleto", "ticket", "enviar un ticket", "reportar un problema",
    "reportar un error", "reportar un fallo", "contactar soporte",
    "solicitar soporte", "presentar una queja", "informar un problema",
]

# Custom Report Builder questions (☰ hamburger menu -> Custom Reports). This
# is a DIFFERENT feature from the chat-driven single-municipality PDF (which
# _is_report_intent in ai_service.py handles via the bare "report" keyword) -
# keep these keywords specific ("custom", "builder", "my own", "elements")
# so they never swallow genuine "generate a report for X" requests.
_CUSTOM_REPORT_KEYWORDS_EN = [
    "custom report", "report builder", "build my own report",
    "build a custom report", "create my own report",
    "custom report builder", "report elements",
]
_CUSTOM_REPORT_KEYWORDS_ES = [
    "informe personalizado", "generador de informes",
    "crear mi propio informe", "constructor de informes",
]

# Phrases that indicate a genuine "how do I use this dashboard" question, as
# opposed to an unrelated "how do I..." question that happens to be phrased
# the same way. Only these fall back to the generic overview steps; anything
# else with no other match is left for the LLM (which has its own scope
# guardrails) instead of guessing.
_GENERAL_DASHBOARD_PHRASES_EN = [
    "use this dashboard", "use the dashboard", "use this site",
    "use this app", "how this works", "how does this work",
    "get started", "getting started", "navigate this",
]
_GENERAL_DASHBOARD_PHRASES_ES = [
    "usar este panel", "usar el panel", "usar este sitio",
    "usar esta aplicación", "usar esta app", "cómo funciona esto",
    "como funciona esto", "empezar", "cómo navego", "como navego",
]


_TEMPLATES_EN = {
    "category_and_municipality": [
        "Step 1: Look at the top of the dashboard and find the Category dropdown.",
        "Step 2: Click it and select \"{category}\".",
        "Step 3: Find the map of Puerto Rico in the center of the page.",
        "Step 4: Click on {municipality} on the map.",
        "Step 5: The right side panel will open with the score and trend chart for {category} in {municipality}.",
    ],
    "category_only": [
        "Step 1: At the top of the dashboard, find the Category dropdown.",
        "Step 2: Click it and select \"{category}\".",
        "Step 3: The map will recolor to show {category} across all municipalities.",
        "Step 4: Click any municipality on the map to see its score and trend chart.",
    ],
    "municipality_only": [
        "Step 1: Find the map of Puerto Rico in the center of the page.",
        "Step 2: Click on {municipality} on the map.",
        "Step 3: The right side panel will open with {municipality}'s score and trend chart.",
        "Step 4: To switch what's being scored, use the Category dropdown at the top of the dashboard.",
    ],
    "general": [
        "Step 1: Use the Category dropdown at the top of the dashboard to choose what to view.",
        "Step 2: Click any municipality on the map of Puerto Rico in the center.",
        "Step 3: The right side panel will show that municipality's score and trend chart.",
        "Step 4: Use this chat to ask for scores, comparisons, or to generate a PDF report.",
    ],
    "report_issue": [
        "Step 1: Click the ⚙ Settings button in the top-right corner of the dashboard.",
        "Step 2: In the panel that opens, click \"\U0001F6DF Report an issue\".",
        "Step 3: Choose a category, add a subject, and describe the issue.",
        "Step 4: Click Submit — our team will follow up by email.",
    ],
    "custom_report_builder": [
        "Step 1: Click the ☰ menu button in the top-left of the header.",
        "Step 2: In the \"Navigation\" panel, click \"Custom Reports\".",
        "Step 3: In the Custom Report Builder that opens, click \"+ Add Element\" to add a report section.",
        "Step 4: For each element, choose its type (Line Graph, Data Table, or Index Breakdown Table), pick one or more municipalities, then a category and indicator, and optionally toggle Normalize/Forecast.",
        "Step 5: Repeat \"+ Add Element\" for as many sections as you want.",
        "Step 6: Click \"Export to PDF\" to print/save your custom report.",
        "(This is different from asking me to generate a report for a specific municipality here in chat.)",
    ],
    "unknown": "I don't see that option in this dashboard yet.",
}

_TEMPLATES_ES = {
    "category_and_municipality": [
        "Paso 1: En la parte superior del panel, busca el menú Categoría.",
        "Paso 2: Haz clic y selecciona \"{category}\".",
        "Paso 3: Busca el mapa de Puerto Rico en el centro de la página.",
        "Paso 4: Haz clic en {municipality} en el mapa.",
        "Paso 5: El panel derecho se abrirá con el puntaje y la gráfica de tendencia para {category} en {municipality}.",
    ],
    "category_only": [
        "Paso 1: En la parte superior del panel, busca el menú Categoría.",
        "Paso 2: Haz clic y selecciona \"{category}\".",
        "Paso 3: El mapa cambiará de color según {category} en todos los municipios.",
        "Paso 4: Haz clic en cualquier municipio del mapa para ver su puntaje y gráfica.",
    ],
    "municipality_only": [
        "Paso 1: Busca el mapa de Puerto Rico en el centro de la página.",
        "Paso 2: Haz clic en {municipality} en el mapa.",
        "Paso 3: El panel derecho se abrirá con los puntajes de {municipality}.",
        "Paso 4: Para cambiar lo que se muestra, usa el menú Categoría en la parte superior.",
    ],
    "general": [
        "Paso 1: Usa el menú Categoría en la parte superior para elegir qué ver.",
        "Paso 2: Haz clic en cualquier municipio del mapa de Puerto Rico.",
        "Paso 3: El panel derecho mostrará el puntaje y la gráfica de ese municipio.",
        "Paso 4: Usa este chat para pedir puntajes, comparaciones o generar un informe en PDF.",
    ],
    "report_issue": [
        "Paso 1: Haz clic en el botón ⚙ Settings en la esquina superior derecha del panel.",
        "Paso 2: En el panel que se abre, haz clic en \"\U0001F6DF Report an issue\".",
        "Paso 3: Elige una categoría, agrega un asunto y describe el problema.",
        "Paso 4: Haz clic en Submit — nuestro equipo responderá por correo electrónico.",
    ],
    "custom_report_builder": [
        "Paso 1: Haz clic en el botón ☰ en la parte superior izquierda del encabezado.",
        "Paso 2: En el panel \"Navigation\", haz clic en \"Custom Reports\".",
        "Paso 3: En el Custom Report Builder que se abre, haz clic en \"+ Add Element\" para agregar una sección al informe.",
        "Paso 4: Para cada elemento, elige su tipo (Line Graph, Data Table o Index Breakdown Table), selecciona uno o más municipios, luego una categoría y un indicador, y activa Normalize/Forecast si lo deseas.",
        "Paso 5: Repite \"+ Add Element\" para agregar tantas secciones como quieras.",
        "Paso 6: Haz clic en \"Export to PDF\" para imprimir o guardar tu informe personalizado.",
        "(Esto es distinto de pedirme que genere un informe para un municipio específico aquí en el chat.)",
    ],
    "unknown": "No veo esa opción en este panel todavía.",
}


def is_navigation_intent(text_lower: str, language: str) -> bool:
    phrases = _NAV_PHRASES_ES if language == "es" else _NAV_PHRASES_EN
    return any(p in text_lower for p in phrases)


def is_custom_report_intent(text_lower: str, language: str) -> bool:
    """Standalone check for the Custom Report Builder feature.

    Not gated by _NAV_PHRASES_EN/ES so it also matches statements like
    "I need a custom report", not just "how do I..." questions. Checked by
    ai_service.py before the generic report-generation keyword match.
    """
    keywords = _CUSTOM_REPORT_KEYWORDS_ES if language == "es" else _CUSTOM_REPORT_KEYWORDS_EN
    return any(kw in text_lower for kw in keywords)


def build_custom_report_response(language: str) -> str:
    templates = _TEMPLATES_ES if language == "es" else _TEMPLATES_EN
    return "\n".join(templates["custom_report_builder"])


_muni_df_cache = None


def _muni_df():
    global _muni_df_cache
    if _muni_df_cache is None:
        conn = get_db_connection()
        try:
            _muni_df_cache = pd.read_sql(
                "SELECT name, fips_code FROM municipalities", conn,
            )
        finally:
            try:
                conn.close()
            except Exception:
                pass
    return _muni_df_cache


def _dropdown_label(table_name: str) -> str:
    # Mirrors layout.py converting underscores to spaces for the dropdown.
    return table_name.replace("_", " ")


def build_navigation_response(user_input: str, language: str) -> str | None:
    """Return numbered UI steps for a confidently-matched navigation question,
    or None if the question doesn't clearly match anything this dashboard can
    do. Callers should fall back to the normal LLM turn (with its own scope
    guardrails) when this returns None, rather than showing a generic guess.
    """
    text_lower = (user_input or "").lower()
    templates = _TEMPLATES_ES if language == "es" else _TEMPLATES_EN

    if any(kw in text_lower for kw in _UNSUPPORTED_KEYWORDS):
        return templates["unknown"]

    ticket_keywords = _TICKET_KEYWORDS_ES if language == "es" else _TICKET_KEYWORDS_EN
    if any(kw in text_lower for kw in ticket_keywords):
        return "\n".join(templates["report_issue"])

    table, _short = detect_category(text_lower)
    category_label = _dropdown_label(table) if table else None

    munis = find_all_municipalities(text_lower, _muni_df())
    muni_name = munis[0]["name"] if munis else None

    if category_label and muni_name:
        steps = templates["category_and_municipality"]
        return "\n".join(
            s.format(category=category_label, municipality=muni_name)
            for s in steps
        )
    if category_label:
        steps = templates["category_only"]
        return "\n".join(s.format(category=category_label) for s in steps)
    if muni_name:
        steps = templates["municipality_only"]
        return "\n".join(s.format(municipality=muni_name) for s in steps)

    general_phrases = (
        _GENERAL_DASHBOARD_PHRASES_ES if language == "es" else _GENERAL_DASHBOARD_PHRASES_EN
    )
    if any(p in text_lower for p in general_phrases):
        return "\n".join(templates["general"])

    # No confident match — let the LLM handle it (and redirect if off-topic)
    # instead of returning generic dashboard steps for an unrelated question.
    return None
