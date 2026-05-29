import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

def update_db():
    try:
        db_url = os.getenv('DATABASE_URL')
        if db_url:
            conn = psycopg2.connect(db_url)
        else:
            conn = psycopg2.connect(
                host=os.getenv('DB_HOST', 'localhost'),
                port=os.getenv('DB_PORT', '5432'),
                database=os.getenv('DB_NAME', 'millionaire'),
                user=os.getenv('DB_USER', 'postgres'),
                password=os.getenv('DB_PASSWORD', '123456')
            )
        with conn.cursor() as cur:
            cur.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id SERIAL PRIMARY KEY,
                transaction_id VARCHAR(100) UNIQUE,
                user_id INT REFERENCES users(user_id) ON DELETE CASCADE,
                amount INT,
                content TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)
        conn.commit()
        print("Transactions table added successfully")
    except Exception as e:
        print(f"Error: {e}")

update_db()
