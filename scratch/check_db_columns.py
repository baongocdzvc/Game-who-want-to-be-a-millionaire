import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()
db_url = os.getenv('DATABASE_URL')
conn = psycopg2.connect(db_url)
with conn.cursor() as cur:
    for table in ['shop_transactions', 'user_wallets', 'users']:
        cur.execute(f"""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = '{table}';
        """)
        cols = cur.fetchall()
        print(f"{table} columns:")
        for col in cols:
            print("  ", col)
conn.close()
