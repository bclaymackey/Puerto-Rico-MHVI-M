import pandas as pd
from tabulate import tabulate
from data import get_db_connection

def run_tests():
    conn = get_db_connection()

    print("\n--- Overall Scores (Top 10) ---")
    df1 = pd.read_sql("""
        SELECT m.name, t.value
        FROM Overall_MHVI_M_Score t
        JOIN municipalities m ON t.fips_code = m.fips_code
        ORDER BY t.year DESC
        LIMIT 10
    """, conn)
    print(tabulate(df1, headers='keys', tablefmt='pretty'))

    print("\n--- Education Scores (Top 10) ---")
    df2 = pd.read_sql("""
        SELECT m.name, t.value
        FROM Education t
        JOIN municipalities m ON t.fips_code = m.fips_code
        ORDER BY t.year DESC
        LIMIT 10
    """, conn)
    print(tabulate(df2, headers='keys', tablefmt='pretty'))

    print("\n--- Healthcare Access (Top 10) ---")
    df3 = pd.read_sql("""
        SELECT m.name, t.value
        FROM Healthcare_Access t
        JOIN municipalities m ON t.fips_code = m.fips_code
        ORDER BY t.year DESC
        LIMIT 10
    """, conn)
    print(tabulate(df3, headers='keys', tablefmt='pretty'))

    conn.close()

if __name__ == "__main__":
    run_tests()