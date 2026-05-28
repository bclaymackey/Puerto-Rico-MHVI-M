"""Lightweight guided-navigation intent.

Detects "how/where do I…" questions about the dashboard and returns short
numbered UI steps instead of running the data or report flow. Templates only
reference UI that actually exists in layout.py (Category dropdown, the map,
the right side panel, this chat).
"""

import pandas as pd

from data import get_db_connection
from data_context_builder import detect_category, find_all_municipalities


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
    "unknown": "No veo esa opción en este panel todavía.",
}


def is_navigation_intent(text_lower: str, language: str) -> bool:
    phrases = _NAV_PHRASES_ES if language == "es" else _NAV_PHRASES_EN
    return any(p in text_lower for p in phrases)


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


def build_navigation_response(user_input: str, language: str) -> str:
    text_lower = (user_input or "").lower()
    templates = _TEMPLATES_ES if language == "es" else _TEMPLATES_EN

    if any(kw in text_lower for kw in _UNSUPPORTED_KEYWORDS):
        return templates["unknown"]

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
    return "\n".join(templates["general"])
