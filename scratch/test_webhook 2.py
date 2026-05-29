import json
import psycopg2
import requests
import sys

# Đọc cấu hình kết nối DB từ .env hoặc mặc định
DB_URL = "postgresql://postgres:123456@localhost:5432/millionaire"
FLASK_URL = "http://127.0.0.1:5001"

def get_test_user():
    """Lấy thông tin một user bất kỳ trong DB để làm mẫu test."""
    try:
        conn = psycopg2.connect(DB_URL)
        with conn.cursor() as cur:
            cur.execute("SELECT user_id, username, plays_left, extra_lifelines FROM users LIMIT 1;")
            user = cur.fetchone()
            if not user:
                print("❌ Không tìm thấy user nào trong database! Vui lòng đăng ký tài khoản trước.")
                sys.exit(1)
            return {
                "user_id": user[0],
                "username": user[1],
                "plays_left": user[2],
                "extra_lifelines": user[3]
            }
    except Exception as e:
        print(f"❌ Không thể kết nối Database: {e}")
        print("Vui lòng đảm bảo PostgreSQL đang chạy và URL trong database là chính xác.")
        sys.exit(1)

def check_user_stats(user_id):
    """Lấy số lượt chơi và trợ giúp hiện tại của user."""
    conn = psycopg2.connect(DB_URL)
    with conn.cursor() as cur:
        cur.execute("SELECT plays_left, extra_lifelines FROM users WHERE user_id = %s;", (user_id,))
        stats = cur.fetchone()
        return stats[0], stats[1]

def main():
    print("=== BẮT ĐẦU KIỂM TRA WEBHOOK SEPAY ===")
    
    # 1. Lấy thông tin user test
    user = get_test_user()
    user_id = user["user_id"]
    print(f"👉 Chọn User test: ID={user_id} | Username='{user['username']}'")
    print(f"   Trạng thái hiện tại: Lượt chơi={user['plays_left']} | Trợ giúp thêm={user['extra_lifelines']}")

    # 2. Tạo payload SePay giả lập
    # Kịch bản 1: Mua Lượt Chơi (ML <user_id>)
    # Số tiền: 15.000 VNĐ -> Thêm 3 lượt (15000 / 5000)
    amount = 15000
    content = f"ML {user_id}"
    transaction_id = f"TEST_TX_{int(psycopg2.connect(DB_URL).cursor().execute('SELECT count(*) FROM transactions;') or 1) + 10000}"
    
    payload = {
        "id": transaction_id,
        "gateway": "Vietinbank",
        "transactionDate": "2026-05-21 00:00:00",
        "accountNumber": "0339422186",
        "subAccount": "",
        "transferType": "in",
        "transferAmount": amount,
        "content": content,
        "referenceCode": "",
        "accumulatedBalance": 10000000
    }

    print(f"\n--- GỬI WEBHOOK GIẢ LẬP ---")
    print(f"Mã giao dịch: {transaction_id}")
    print(f"Số tiền: {amount:,} VNĐ | Nội dung: '{content}'")
    
    webhook_url = f"{FLASK_URL}/api/webhook/sepay"
    try:
        resp = requests.post(webhook_url, json=payload, timeout=5)
        print(f"Phản hồi từ Flask: HTTP {resp.status_code}")
        print(f"Response: {resp.text}")
        
        if resp.status_code == 200:
            # 3. Kiểm tra xem DB đã cập nhật chưa
            new_plays, new_lifelines = check_user_stats(user_id)
            print(f"\n--- KẾT QUẢ SAU WEBHOOK ---")
            print(f"Lượt chơi cũ: {user['plays_left']} -> Mới: {new_plays} (Tăng: {new_plays - user['plays_left']})")
            print(f"Trợ giúp cũ: {user['extra_lifelines']} -> Mới: {new_lifelines}")
            
            if new_plays > user['plays_left']:
                print("✅ THÀNH CÔNG: Webhook nhận diện và cộng lượt chơi thành công!")
            else:
                print("❌ THẤT BẠI: Webhook chạy không lỗi nhưng lượt chơi không tăng. Vui lòng check log Flask!")
        else:
            print("❌ LỖI: Flask không trả về HTTP 200.")
    except requests.exceptions.ConnectionError:
        print(f"❌ KHÔNG THỂ KẾT NỐI TỚI FLASK tại {FLASK_URL}")
        print("Hãy chạy 'python3 app.py' trước khi chạy script test này.")

if __name__ == "__main__":
    main()
