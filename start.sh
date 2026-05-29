#!/bin/bash
# ═══════════════════════════════════════════
#  AI LÀ TRIỆU PHÚ — SCRIPT KHỞI ĐỘNG
#  Chạy lệnh: bash start.sh
# ═══════════════════════════════════════════

# Dùng Python để đọc .env an toàn (xử lý comment tiếng Việt)
read_env() {
  python3 -c "
import re, sys
key = sys.argv[1]
with open('.env') as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith('#'): continue
        # Tách KEY=VALUE, bỏ phần comment inline
        m = re.match(r'^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)', line)
        if not m: continue
        k, v = m.group(1), m.group(2)
        # Bỏ comment inline (phần sau # không nằm trong quotes)
        v = re.sub(r'\s+#.*$', '', v).strip()
        if k == key:
            print(v)
            break
" "$1" 2>/dev/null
}

NGROK_AUTHTOKEN=$(read_env NGROK_AUTHTOKEN)
NGROK_URL=$(read_env NGROK_URL)
WEBHOOK_SECRET=$(read_env WEBHOOK_SECRET)

echo "══════════════════════════════════════════"
echo "🎮 AI LÀ TRIỆU PHÚ — KHỞI ĐỘNG HỆ THỐNG"
echo "══════════════════════════════════════════"

# Giải phóng port 5001 nếu đang bận
lsof -ti :5001 | xargs kill -9 2>/dev/null && echo "✅ Đã giải phóng port 5001" || true

# 1. Kiểm tra authtoken ngrok
if [ -z "$NGROK_AUTHTOKEN" ]; then
  echo ""
  echo "⚠️  NGROK_AUTHTOKEN chưa được cấu hình trong file .env!"
  echo ""
  echo "👉 Hướng dẫn lấy authtoken:"
  echo "   1. Truy cập: https://dashboard.ngrok.com/get-started/your-authtoken"
  echo "   2. Copy authtoken"
  echo "   3. Dán vào dòng NGROK_AUTHTOKEN= trong file .env"
  echo ""
  echo "💡 Sau khi cấu hình, chạy lại: bash start.sh"
  echo ""
  echo "📌 (Hoặc chỉ chạy Flask không có webhook: python3 app.py)"
  exit 1
fi

# 2. Cấu hình authtoken cho ngrok
echo "🔑 Đang cấu hình ngrok authtoken..."
./ngrok authtoken "$NGROK_AUTHTOKEN" 2>/dev/null || true

# 3. Khởi động ngrok tunnel trong nền
echo "🌍 Đang khởi động ngrok tunnel..."
./ngrok http 5001 > /tmp/ngrok.log 2>&1 &
NGROK_PID=$!

# Chờ ngrok khởi động (tối đa 8 giây)
for i in 1 2 3 4 5 6 7 8; do
  sleep 1
  NGROK_PUBLIC_URL=$(curl -s http://localhost:4040/api/tunnels 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); tunnels=d.get('tunnels',[]); print(next((t['public_url'] for t in tunnels if t['public_url'].startswith('https')), ''))" 2>/dev/null)
  if [ -n "$NGROK_PUBLIC_URL" ]; then break; fi
done

echo ""
echo "══════════════════════════════════════════"
if [ -n "$NGROK_PUBLIC_URL" ]; then
  echo "✅ NGROK đang chạy!"
  echo ""
  echo "📡 URL công khai: $NGROK_PUBLIC_URL"
  echo ""
  echo "🔧 CẤU HÌNH WEBHOOK TRÊN SEPAY.VN:"
  echo "   URL:  $NGROK_PUBLIC_URL/api/shop/webhook"
  echo "   Xác thực: Apikey"
  echo "   Giá trị:  $WEBHOOK_SECRET"
else
  echo "⚠️  Không lấy được URL ngrok."
  echo "   Kiểm tra tại: http://localhost:4040"
fi
echo "══════════════════════════════════════════"
echo ""
echo "🚀 Khởi động Flask server tại http://localhost:5001 ..."
echo ""

# 4. Khởi động Flask server
python3 app.py

# Dọn dẹp ngrok khi Flask thoát
kill $NGROK_PID 2>/dev/null
