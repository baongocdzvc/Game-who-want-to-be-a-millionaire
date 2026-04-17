"""
setup_database.py
Kết nối PostgreSQL, tạo tables: users, user_passwords, rankings, game_history
"""

import psycopg2
import bcrypt
import os
from psycopg2 import sql
from dotenv import load_dotenv

# Load biến môi trường từ file .env
load_dotenv()

# ============================================================
# HÀM: KẾT NỐI DATABASE
# ============================================================
def get_connection():
    """Tạo và trả về kết nối tới PostgreSQL."""
    try:
        # Ưu tiên dùng DATABASE_URL từ .env
        db_url = os.getenv('DATABASE_URL')
        if db_url:
            conn = psycopg2.connect(db_url)
        else:
            # Fallback nếu không có URL
            conn = psycopg2.connect(
                host=os.getenv('DB_HOST', 'localhost'),
                port=os.getenv('DB_PORT', '5432'),
                database=os.getenv('DB_NAME', 'millionaire'),
                user=os.getenv('DB_USER', 'postgres'),
                password=os.getenv('DB_PASSWORD', '123456')
            )
        # print("✅ Kết nối database thành công!")
        return conn

    except Exception as e:
        print(f"❌ Không thể kết nối database: {e}")
        print("Mẹo: Hãy kiểm tra DATABASE_URL trong file .env hoặc đảm bảo PostgreSQL đang chạy.")
        return None

# ============================================================
# SQL: TẠO TABLES
# ============================================================
SQL_CREATE_TABLES = """
-- 1. BẢNG USERS
CREATE TABLE IF NOT EXISTS users (
    user_id      SERIAL PRIMARY KEY,
    username     VARCHAR(50)  UNIQUE NOT NULL,
    email        VARCHAR(100) UNIQUE NOT NULL,
    full_name    VARCHAR(100),
    avatar_url   TEXT,
    is_active    BOOLEAN      DEFAULT TRUE,
    created_at   TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    updated_at   TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
);

-- 2. BẢNG PASSWORDS (tách riêng để bảo mật)
CREATE TABLE IF NOT EXISTS user_passwords (
    password_id   SERIAL PRIMARY KEY,
    user_id       INT          UNIQUE NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    password_hash TEXT         NOT NULL,
    salt          VARCHAR(255),
    last_changed  TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    must_change   BOOLEAN      DEFAULT FALSE
);

-- 3. BẢNG XẾP HẠNG
CREATE TABLE IF NOT EXISTS rankings (
    ranking_id   SERIAL PRIMARY KEY,
    user_id      INT          UNIQUE NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    total_score  INT          DEFAULT 0,
    total_wins   INT          DEFAULT 0,
    total_losses INT          DEFAULT 0,
    total_draws  INT          DEFAULT 0,
    win_rate     NUMERIC(5,2) DEFAULT 0.00,
    rank_title   VARCHAR(50)  DEFAULT 'Newcomer',
    rank_points  INT          DEFAULT 0,
    updated_at   TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
);

-- 4. BẢNG LỊCH SỬ CHƠI
CREATE TABLE IF NOT EXISTS game_history (
    history_id   SERIAL PRIMARY KEY,
    user_id      INT          NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    game_mode    VARCHAR(50),
    result       VARCHAR(10)  CHECK (result IN ('win', 'loss', 'draw')),
    score        INT          DEFAULT 0,
    duration_sec INT,
    opponent_id  INT          REFERENCES users(user_id),
    metadata     JSONB,
    played_at    TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
);

-- 5. BẢNG MÃ KHÔI PHỤC MẬT KHẨU
CREATE TABLE IF NOT EXISTS password_reset_codes (
    code_id      SERIAL PRIMARY KEY,
    user_id      INT          NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    code         VARCHAR(6)   NOT NULL,
    created_at   TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    expires_at   TIMESTAMP    NOT NULL,
    is_used      BOOLEAN      DEFAULT FALSE
);

"""

# ============================================================
# SQL: INDEX
# ============================================================
SQL_CREATE_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_rankings_score     ON rankings(total_score DESC);
CREATE INDEX IF NOT EXISTS idx_rankings_points    ON rankings(rank_points DESC);
CREATE INDEX IF NOT EXISTS idx_history_user       ON game_history(user_id);
CREATE INDEX IF NOT EXISTS idx_history_played_at  ON game_history(played_at DESC);
"""

# ============================================================
# SQL: TRIGGER tự động cập nhật win_rate
# ============================================================
SQL_CREATE_TRIGGER = """
CREATE OR REPLACE FUNCTION update_win_rate()
RETURNS TRIGGER AS $$
BEGIN
    IF (NEW.total_wins + NEW.total_losses + NEW.total_draws) > 0 THEN
        NEW.win_rate := ROUND(
            NEW.total_wins::NUMERIC /
            (NEW.total_wins + NEW.total_losses + NEW.total_draws) * 100, 2
        );
    END IF;
    NEW.updated_at := CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_win_rate ON rankings;
CREATE TRIGGER trg_win_rate
BEFORE UPDATE ON rankings
FOR EACH ROW EXECUTE FUNCTION update_win_rate();
"""

# ============================================================
# HÀM: TẠO TABLES, INDEX, TRIGGER
# ============================================================
def create_schema(conn):
    """Tạo toàn bộ schema: tables, indexes, triggers."""
    with conn.cursor() as cur:
        print("\n📦 Đang tạo tables...")
        cur.execute(SQL_CREATE_TABLES)

        print("🔍 Đang tạo indexes...")
        cur.execute(SQL_CREATE_INDEXES)

        print("⚙️  Đang tạo trigger win_rate...")
        cur.execute(SQL_CREATE_TRIGGER)

    conn.commit()
    print("✅ Tạo schema thành công!\n")

# ============================================================
# HÀM: THÊM DỮ LIỆU MẪU
# ============================================================
def insert_sample_data(conn):
    """Thêm một user mẫu cùng password, ranking, lịch sử chơi."""
    with conn.cursor() as cur:
        # Kiểm tra user đã tồn tại chưa
        cur.execute("SELECT user_id FROM users WHERE username = %s", ("player01",))
        if cur.fetchone():
            print("ℹ️  Dữ liệu mẫu đã tồn tại (player01), bỏ qua bước này.")
            return

        # Thêm user
        cur.execute("""
            INSERT INTO users (username, email, full_name)
            VALUES (%s, %s, %s)
            RETURNING user_id
        """, ("player01", "player01@email.com", "Nguyen Van A"))
        user_id = cur.fetchone()[0]

        # Hash password bằng bcrypt
        hashed = bcrypt.hashpw("SecurePass123".encode(), bcrypt.gensalt()).decode()
        cur.execute("""
            INSERT INTO user_passwords (user_id, password_hash)
            VALUES (%s, %s)
        """, (user_id, hashed))

        # Khởi tạo ranking
        cur.execute("""
            INSERT INTO rankings (user_id, total_wins, total_losses, rank_title, rank_points)
            VALUES (%s, 5, 2, 'Bronze', 150)
        """, (user_id,))

        # Thêm 3 lịch sử chơi
        sample_games = [
            (user_id, "pvp",   "win",  150, 320),
            (user_id, "solo",  "loss",  80, 180),
            (user_id, "pvp",   "win",  200, 410),
        ]
        cur.executemany("""
            INSERT INTO game_history (user_id, game_mode, result, score, duration_sec)
            VALUES (%s, %s, %s, %s, %s)
        """, sample_games)

    conn.commit()
    print(f"✅ Đã thêm dữ liệu mẫu cho user_id={user_id}")

# ============================================================
# MAIN
# ============================================================
def main():
    conn = get_connection()
    if not conn:
        return

    try:
        create_schema(conn)
        insert_sample_data(conn)
        print("\n🎉 Toàn bộ quá trình khởi tạo dữ liệu đã hoàn tất!")
    finally:
        conn.close()
        print("🔒 Đã đóng kết nối database.")

if __name__ == "__main__":
    main()