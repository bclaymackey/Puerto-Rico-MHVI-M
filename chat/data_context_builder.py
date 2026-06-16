import re

import pandas as pd

from data import get_db_connection, ALLOWED_TABLES


CATEGORY_KEYWORDS = [
    # English
    ("health care",       "Healthcare_Access",              "Healthcare"),
    ("healthcare",        "Healthcare_Access",              "Healthcare"),
    ("health risk",       "Health_Risk_Behaviors",          "Health Risk"),
    ("built environment", "Neighborhood_Built_Environment", "Neighborhood"),
    ("neighborhood",      "Neighborhood_Built_Environment", "Neighborhood"),
    ("transportation",    "Transportation_Accessibility",   "Transportation"),
    ("transit",           "Transportation_Accessibility",   "Transportation"),
    ("employment",        "Economic_Employment",            "Employment"),
    ("economic",          "Economic_Employment",            "Employment"),
    ("jobs",              "Economic_Employment",            "Employment"),
    ("education",         "Education",                      "Education"),
    ("housing",           "Housing",                        "Housing"),
    ("food",              "Food_Water_Basic_Needs",         "Food & Basic Needs"),
    ("water",             "Food_Water_Basic_Needs",         "Food & Basic Needs"),
    ("basic needs",       "Food_Water_Basic_Needs",         "Food & Basic Needs"),
    ("social",            "Social_Relationships_Community", "Social & Community"),
    ("community",         "Social_Relationships_Community", "Social & Community"),
    ("trauma",            "Trauma_Violence_Adversity",      "Trauma & Violence"),
    ("violence",          "Trauma_Violence_Adversity",      "Trauma & Violence"),
    # Spanish
    ("acceso médico",     "Healthcare_Access",              "Healthcare"),
    ("acceso medico",     "Healthcare_Access",              "Healthcare"),
    ("atención médica",   "Healthcare_Access",              "Healthcare"),
    ("atencion medica",   "Healthcare_Access",              "Healthcare"),
    ("salud",             "Healthcare_Access",              "Healthcare"),
    ("conducta de riesgo","Health_Risk_Behaviors",          "Health Risk"),
    ("riesgo de salud",   "Health_Risk_Behaviors",          "Health Risk"),
    ("entorno construido","Neighborhood_Built_Environment", "Neighborhood"),
    ("vecindario",        "Neighborhood_Built_Environment", "Neighborhood"),
    ("barrio",            "Neighborhood_Built_Environment", "Neighborhood"),
    ("transporte",        "Transportation_Accessibility",   "Transportation"),
    ("empleo",            "Economic_Employment",            "Employment"),
    ("económico",         "Economic_Employment",            "Employment"),
    ("economico",         "Economic_Employment",            "Employment"),
    ("trabajo",           "Economic_Employment",            "Employment"),
    ("educación",         "Education",                      "Education"),
    ("educacion",         "Education",                      "Education"),
    ("vivienda",          "Housing",                        "Housing"),
    ("comida",            "Food_Water_Basic_Needs",         "Food & Basic Needs"),
    ("alimentos",         "Food_Water_Basic_Needs",         "Food & Basic Needs"),
    ("agua",              "Food_Water_Basic_Needs",         "Food & Basic Needs"),
    ("necesidades básicas","Food_Water_Basic_Needs",        "Food & Basic Needs"),
    ("necesidades basicas","Food_Water_Basic_Needs",        "Food & Basic Needs"),
    ("comunidad",         "Social_Relationships_Community", "Social & Community"),
    ("relaciones sociales","Social_Relationships_Community", "Social & Community"),
    ("violencia",         "Trauma_Violence_Adversity",      "Trauma & Violence"),
    ("adversidad",        "Trauma_Violence_Adversity",      "Trauma & Violence"),
]

OVERALL_KEYWORDS = [
    "overall", "overall score", "vulnerability index", "vulnerability score",
    "vulnerable",
    "puntaje general", "puntuación general", "puntuacion general",
    "índice general", "indice general", "índice de vulnerabilidad",
    "indice de vulnerabilidad", "score general", "vulnerabilidad",
]

COMPARISON_KEYWORDS = [
    "compare", "comparison", "comparing", "compared",
    "versus", " vs ", " vs.", "side by side", "side-by-side",
    "difference between", "differences between",
    "comparar", "comparación", "comparacion", "compara", "comparado",
    "contra", "frente a", "diferencia entre", "diferencias entre",
]

RANKING_KEYWORDS = [
    "which municipalities", "what municipalities",
    "highest vulnerability", "most vulnerable",
    "top municipalities", "rank municipalities", "ranking",
    "qué municipios", "que municipios",
    "cuáles municipios", "cuales municipios",
    "cuáles son los municipios", "cuales son los municipios",
    "mayor vulnerabilidad", "más vulnerables", "mas vulnerables",
    "municipios más vulnerables", "municipios mas vulnerables",
]


def _is_comparison_query(text_lower: str) -> bool:
    padded = f" {text_lower} "
    return any(kw in padded for kw in COMPARISON_KEYWORDS)


def _is_overall_query(text_lower: str) -> bool:
    return any(kw in text_lower for kw in OVERALL_KEYWORDS)


def _is_ranking_query(text_lower: str) -> bool:
    return any(kw in text_lower for kw in RANKING_KEYWORDS)


def _detect_category(text_lower: str):
    for keyword, table, display in CATEGORY_KEYWORDS:
        if keyword in text_lower and table in ALLOWED_TABLES:
            return table, display
    return None, None


def detect_category(text_lower: str):
    """Public wrapper around _detect_category."""
    return _detect_category(text_lower)


def find_all_municipalities(text_lower: str, muni_df: pd.DataFrame) -> list:
    """Return municipalities mentioned in the message, in order of appearance.

    Longest names matched first to avoid partial overlaps (e.g. "San Juan"
    before "Juan Díaz"). Each FIPS is returned at most once.
    """
    sorted_munis = sorted(
        muni_df.to_dict("records"),
        key=lambda r: len(r["name"]),
        reverse=True,
    )

    occupied = [False] * len(text_lower)
    candidates = []

    for row in sorted_munis:
        name_lower = row["name"].lower()
        pattern = r"\b" + re.escape(name_lower) + r"\b"
        for m in re.finditer(pattern, text_lower):
            start, end = m.start(), m.end()
            if any(occupied[i] for i in range(start, end)):
                continue
            for i in range(start, end):
                occupied[i] = True
            candidates.append((start, row["name"], row["fips_code"]))

    candidates.sort(key=lambda c: c[0])

    found = []
    seen = set()
    for _, name, fips in candidates:
        if fips in seen:
            continue
        seen.add(fips)
        found.append({"name": name, "fips_code": fips})
    return found


def _fetch_overall_score(conn, fips):
    df = pd.read_sql(
        """
        SELECT value
        FROM Overall_MHVI_M_Score
        WHERE fips_code = ?
        ORDER BY year DESC
        LIMIT 1
        """,
        conn,
        params=(fips,),
    )
    if df.empty:
        return None
    return round(df["value"][0], 2)


def _fetch_category_score(conn, fips, table):
    df = pd.read_sql(
        f"""
        SELECT value
        FROM {table}
        WHERE fips_code = ? AND indicator_name = ?
        ORDER BY year DESC
        LIMIT 1
        """,
        conn,
        params=(fips, "Subcategory Index Score"),
    )
    if df.empty:
        return None
    return round(df["value"][0], 2)


def _top_municipalities(conn, limit: int = 5) -> pd.DataFrame:
    return pd.read_sql(
        """
        SELECT m.name, o.value
        FROM Overall_MHVI_M_Score o
        JOIN municipalities m ON o.fips_code = m.fips_code
        WHERE o.year = (SELECT MAX(year) FROM Overall_MHVI_M_Score)
        ORDER BY o.value DESC
        LIMIT ?
        """,
        conn,
        params=(limit,),
    )


_HIGHER_NOTE = "Higher score means higher vulnerability."


def get_data_context(user_input: str, language: str = "en") -> str:
    """Return a plain-string snapshot of relevant data, or "" if nothing matched.

    The LLM uses this together with recent chat history to answer.
    """
    user_input_lower = user_input.lower()
    conn = None

    try:
        conn = get_db_connection()

        muni_df = pd.read_sql(
            "SELECT name, fips_code FROM municipalities", conn,
        )
        found_munis = find_all_municipalities(user_input_lower, muni_df)

        # COMPARISON FLOW — two or more municipalities mentioned.
        if len(found_munis) >= 2:
            cat_search = user_input_lower
            for m in found_munis:
                cat_search = cat_search.replace(m["name"].lower(), " ")

            table, display = _detect_category(cat_search)
            wants_overall = _is_overall_query(user_input_lower)

            if table:
                pairs = []
                missing = []
                for m in found_munis:
                    val = _fetch_category_score(conn, m["fips_code"], table)
                    if val is not None:
                        pairs.append(f"{m['name']} {display} score: {val}")
                    else:
                        missing.append(m["name"])
                if pairs:
                    return ". ".join(pairs) + f". {_HIGHER_NOTE}"
                return f"No {display} data found for {', '.join(missing)}."

            if wants_overall or _is_comparison_query(user_input_lower):
                pairs = []
                missing = []
                for m in found_munis:
                    val = _fetch_overall_score(conn, m["fips_code"])
                    if val is not None:
                        pairs.append(
                            f"{m['name']} overall vulnerability score: {val}"
                        )
                    else:
                        missing.append(m["name"])
                if pairs:
                    return ". ".join(pairs) + f". {_HIGHER_NOTE}"
                return f"No overall score data found for {', '.join(missing)}."

        # RANKING — no specific municipality, ranking-style question.
        if not found_munis and _is_ranking_query(user_input_lower):
            df = _top_municipalities(conn, limit=5)
            if not df.empty:
                pairs = [
                    f"{row['name']} ({round(row['value'], 2)})"
                    for _, row in df.iterrows()
                ]
                return (
                    "Top 5 most vulnerable municipalities (latest year), "
                    "ordered from most to least vulnerable: "
                    + ", ".join(pairs)
                    + f". {_HIGHER_NOTE}"
                )

        # SINGLE MUNICIPALITY — overall.
        if len(found_munis) == 1 and _is_overall_query(user_input_lower):
            m = found_munis[0]
            val = _fetch_overall_score(conn, m["fips_code"])
            if val is not None:
                return (
                    f"{m['name']} overall vulnerability score: {val}. "
                    f"{_HIGHER_NOTE}"
                )
            return f"No overall score data found for {m['name']}."

        # SINGLE MUNICIPALITY — category.
        if len(found_munis) == 1:
            m = found_munis[0]
            cat_search = user_input_lower.replace(m["name"].lower(), " ")
            table, display = _detect_category(cat_search)
            if table:
                val = _fetch_category_score(conn, m["fips_code"], table)
                if val is not None:
                    return (
                        f"{m['name']} {display} score: {val}. {_HIGHER_NOTE}"
                    )
                return f"No {display} data found for {m['name']}."

        return ""

    except Exception as e:
        print(e)
        return ""

    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
