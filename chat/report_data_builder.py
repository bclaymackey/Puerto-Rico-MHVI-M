import pandas as pd

from data import get_db_connection, ALLOWED_TABLES


CATEGORY_DISPLAY_NAMES = {
    "Economic_Employment": "Employment",
    "Education": "Education",
    "Food_Water_Basic_Needs": "Food & Basic Needs",
    "Health_Risk_Behaviors": "Health Risk Behaviors",
    "Healthcare_Access": "Healthcare Access",
    "Housing": "Housing",
    "Neighborhood_Built_Environment": "Neighborhood & Built Environment",
    "Social_Relationships_Community": "Social & Community",
    "Transportation_Accessibility": "Transportation",
    "Trauma_Violence_Adversity": "Trauma & Violence",
}


def _lookup_fips(conn, municipality: str):
    df = pd.read_sql(
        "SELECT name, fips_code FROM municipalities WHERE LOWER(name) = LOWER(?)",
        conn,
        params=(municipality.strip(),),
    )
    if df.empty:
        return None, None
    return df["name"][0], df["fips_code"][0]


def _fetch_overall(conn, fips):
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
    if df.empty or df["value"][0] is None:
        return None
    return round(float(df["value"][0]), 2)


def _fetch_category(conn, fips, table):
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
    if df.empty or df["value"][0] is None:
        return None
    return round(float(df["value"][0]), 2)


def get_report_data(municipality: str) -> dict:
    """Return latest-year overall + per-category scores for a municipality.

    Returns {} if the municipality is unknown. Categories with no data
    are omitted from the result rather than included with a null value,
    so the LLM never sees missing numbers.
    """
    if not municipality:
        return {}

    conn = None
    try:
        conn = get_db_connection()
        canonical_name, fips = _lookup_fips(conn, municipality)
        if not fips:
            return {}

        overall = _fetch_overall(conn, fips)

        categories = {}
        for table in ALLOWED_TABLES:
            if table == "Overall_MHVI_M_Score":
                continue
            display = CATEGORY_DISPLAY_NAMES.get(table, table.replace("_", " "))
            value = _fetch_category(conn, fips, table)
            if value is not None:
                categories[display] = value

        return {
            "municipality": canonical_name,
            "fips_code": fips,
            "overall_score": overall,
            "categories": categories,
            "higher_is_more_vulnerable": True,
        }
    except Exception as e:
        print(f"[get_report_data] error: {e}")
        return {}
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


if __name__ == "__main__":
    import json
    print(json.dumps(get_report_data("Arecibo"), indent=2))
