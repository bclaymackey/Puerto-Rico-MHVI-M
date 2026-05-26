import sqlite3
import pandas as pd

db_path = r'C:\Users\bthem\Documents\AI_Masters\GRA\pr_dashboard.db'

def create_data_dictionary():
    print("Connecting to database...")
    conn = sqlite3.connect(db_path)
    
    # Get all tables
    tables_query = "SELECT name FROM sqlite_master WHERE type='table' AND name NOT IN ('municipalities', 'sqlite_sequence', 'Overall_MHVI_M_Score', 'Data_Dictionary')"
    tables = pd.read_sql_query(tables_query, conn)['name'].tolist()
    
    print(f"Found {len(tables)} category tables.")
    
    all_indicators = []
    
    for tbl in tables:
        try:
            inds = pd.read_sql_query(f"SELECT DISTINCT indicator_name FROM {tbl}", conn)['indicator_name'].tolist()
            for ind in inds:
                if ind != 'Subcategory Index Score':
                    all_indicators.append({
                        'raw_name': ind,
                        'category': tbl,
                        'friendly_name': ind.replace('_', ' ').title(),
                        'description': f"Data for {ind.replace('_', ' ').lower()}.",
                        'source': "Puerto Rico Open Data / US Census"
                    })
        except Exception as e:
            print(f"Error reading table {tbl}: {e}")
            
    if not all_indicators:
        print("No indicators found. Exiting.")
        conn.close()
        return
        
    df_dict = pd.DataFrame(all_indicators)
    df_dict.drop_duplicates(subset=['raw_name'], inplace=True)
    
    print(f"Compiled {len(df_dict)} unique indicators. Writing to Data_Dictionary table...")
    df_dict.to_sql('Data_Dictionary', conn, if_exists='replace', index=False)
    
    print("Data Dictionary created successfully!")
    conn.close()

if __name__ == '__main__':
    create_data_dictionary()
