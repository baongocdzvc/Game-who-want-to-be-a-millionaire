import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

def create_db():
    try:
        # Kết nối tới database 'postgres' mặc định để tạo database mới
        conn = psycopg2.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            port=os.getenv('DB_PORT', '5432'),
            database='postgres',
            user=os.getenv('DB_USER', 'postgres'),
            password=os.getenv('DB_PASSWORD', '123456')
        )
        conn.autocommit = True
        cur = conn.cursor()
        
        # Tạo database
        cur.execute("CREATE DATABASE millionaire;")
        print("✅ Đã tạo database 'millionaire' thành công!")
        
        cur.close()
        conn.close()
    except Exception as e:
        if "already exists" in str(e):
            print("ℹ️  Database 'millionaire' đã tồn tại.")
        else:
            print(f"❌ Lỗi khi tạo database: {e}")

if __name__ == "__main__":
    create_db()
