"""
==========================================
AI LÀ TRIỆU PHÚ - BACKEND SERVER
==========================================
File: app.py
Ngôn ngữ: Python + Flask
Mô tả: Server API xử lý logic game, quản lý phiên chơi, chatbot
==========================================
"""

import os
import json
import random
import uuid
import time
import html
import hashlib
import urllib.request
import urllib.parse
import smtplib
import bcrypt
import psycopg2
import psycopg2.extras
from email.mime.text import MIMEText
from email.header import Header
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, jsonify, request, render_template, send_from_directory, session, redirect
from flask_cors import CORS
from dotenv import load_dotenv
from google import genai
from database import get_connection, SQL_CREATE_TABLES, create_schema



# Tải file .env để lấy API Key
load_dotenv()

# Khởi tạo Gemini Client (Cần có GEMINI_API_KEY trong .env)
try:
    api_key = os.environ.get('GEMINI_API_KEY')
    if api_key:
        gemini_client = genai.Client(api_key=api_key)
    else:
        gemini_client = None
        print("Cảnh báo: Không tìm thấy GEMINI_API_KEY trong .env")
except Exception as e:
    gemini_client = None
    print(f"Lỗi khởi tạo Gemini (Vui lòng kiểm tra GEMINI_API_KEY): {e}")

# Mẫu model ổn định
GEMINI_MODEL = 'models/gemini-flash-latest'






# === CẤU HÌNH GỬI EMAIL (Quên mật khẩu) ===
MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
MAIL_USERNAME = os.environ.get('MAIL_USERNAME', '') # Nhập email của bạn vào .env
MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', '') # Nhập App Password vào .env
MAIL_SENDER = os.environ.get('MAIL_SENDER', 'Ai Là Triệu Phú Support <support@millionaire.com>')

def send_email_code(receiver_email, code):
    """Gửi mã xác nhận 6 số qua email."""
    subject = "Mã xác nhận khôi phục mật khẩu - Ai Là Triệu Phú"
    body = f"Chào bạn,\n\nMã xác nhận của bạn để đặt lại mật khẩu là: {code}\n\nMã này sẽ hết hạn sau 15 phút. Nếu không phải bạn yêu cầu, vui lòng bỏ qua email này."
    
    # In ra terminal để debug (nếu cấu hình email chưa chuẩn vẫn thấy mã)
    print(f"\n[EMAIL SIMULATION] Gửi tới {receiver_email}: Mã của bạn là {code}\n")
    
    if not MAIL_USERNAME or not MAIL_PASSWORD:
        return True # Giả lập thành công

    try:
        msg = MIMEText(body, 'plain', 'utf-8')
        msg['Subject'] = Header(subject, 'utf-8')
        msg['From'] = MAIL_SENDER
        msg['To'] = receiver_email
        
        server = smtplib.SMTP(MAIL_SERVER, MAIL_PORT)
        server.starttls()
        server.login(MAIL_USERNAME, MAIL_PASSWORD)
        server.sendmail(MAIL_USERNAME, receiver_email, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"Lỗi gửi email: {e}")
        return False

# === KHỞI TẠO ỨNG DỤNG FLASK ===

# static_folder: thư mục chứa file CSS, JS, hình ảnh
# template_folder: thư mục chứa file HTML
app = Flask(__name__,
            static_folder='static',
            template_folder='templates')

# Secret key cho Flask session (lưu trạng thái đăng nhập)
app.secret_key = os.environ.get('SECRET_KEY', 'millionaire-secret-2026-xK9mP')

# === CẤU HÌNH SEPAY ===
def clean_env(val, default=""):
    if not val:
        return default
    # Loại bỏ comment nếu có (ví dụ: # comment)
    val = str(val).split('#')[0]
    return val.strip()

SEPAY_BANK_CODE    = clean_env(os.environ.get('SEPAY_BANK_CODE'), 'MBBank')      # Mã ngân hàng: VCB, TCB, MBBank, VPBank...
SEPAY_ACCOUNT_NO   = clean_env(os.environ.get('SEPAY_ACCOUNT_NO'), '0123456789') # Số tài khoản
SEPAY_ACCOUNT_NAME = clean_env(os.environ.get('SEPAY_ACCOUNT_NAME'), 'AI LA TRIEU PHU') # Tên chủ TK
WEBHOOK_SECRET     = clean_env(os.environ.get('WEBHOOK_SECRET'), 'dev-secret-123')

# Cho phép Cross-Origin
CORS(app, supports_credentials=True)

# === LƯU TRRỮNG THÔNG TIN NGƯỚI DÙNG (DATABASE) ===
def get_db():
    return get_connection()

def get_or_create_wallet(cur, user_id):
    cur.execute("SELECT game_turns, bonus_lifelines FROM user_wallets WHERE user_id = %s", (user_id,))
    row = cur.fetchone()
    if row:
        return dict(row)
    else:
        cur.execute("""
            INSERT INTO user_wallets (user_id, game_turns, bonus_lifelines)
            VALUES (%s, 3, 0)
            ON CONFLICT (user_id) DO NOTHING
        """, (user_id,))
        return {'game_turns': 3, 'bonus_lifelines': 0}

def hash_password(pw):
    return bcrypt.hashpw(pw.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def check_password(pw, hashed):
    return bcrypt.checkpw(pw.encode('utf-8'), hashed.encode('utf-8'))


def login_required(f):
    """Decorator bảo vệ route - yêu cầu đăng nhập trước"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'username' not in session:
            return redirect('/auth')
        return f(*args, **kwargs)
    return decorated

# === CÁC MỨC TIỀN THƯỞNG (15 mức) ===
PRIZE_LEVELS = [
    "200.000 đ", "400.000 đ", "600.000 đ", "1.000.000 đ", "2.000.000 đ",
    "3.000.000 đ", "6.000.000 đ", "10.000.000 đ", "14.000.000 đ", "22.000.000 đ",
    "30.000.000 đ", "40.000.000 đ", "60.000.000 đ", "85.000.000 đ", "150.000.000 đ"
]

# Mốc an toàn: câu 5 (index 4) và câu 10 (index 9)
MILESTONES = [4, 9]

# === SINH CÂU HỎI QUA AI TỰ ĐỘNG ===
def generate_questions_with_ai():
    """Dùng Gemini AI để tạo ra 15 câu hỏi mới theo độ khó."""
    if not gemini_client:
        return None

    # NGUYÊN LÝ HOÀN ĐỘNG (Prompt Cơ Bản):
    # 1. Đóng vai (Roleplay): Thiết lập AI là chuyên gia của game "Ai Là Triệu Phú".
    # 2. Định mục tiêu (Objective): Yêu cầu tạo đủ 15 câu theo đúng 3 mức độ khó (Dễ, TB, Khó).
    # 3. Định dạng đầu ra (Output Constraint): Ép AI trả về JSON thuần túy để code Python có thể đọc được ngay (json.loads).
    # 4. Tránh rác (Filtering): Yêu cầu không kèm text giải thích để tránh lỗi cú pháp khi parse.
    prompt = '''Bạn là một chuyên gia trí tuệ của hệ thống "Ai Là Triệu Phú".
Nhiệm vụ: Sáng tác đủ 15 câu hỏi trắc nghiệm bằng Tiếng Việt.
Phân bổ độ khó: 5 câu dễ, 5 trung bình, 5 khó.
Cấu trúc JSON: [{"difficulty": "easy/medium/hard", "question": "...", "answers": ["A", "B", "C", "D"], "correct": 0-3}]
Chỉ trả về JSON, không kèm text khác.
'''
    try:
        response = gemini_client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
        )
        # Sửa lỗi Warning non-text parts bằng cách chỉ lấy phần text
        res_text = "".join([part.text for part in response.candidates[0].content.parts if part.text or ""])
        res_text = res_text.strip()
        
        # Lọc JSON
        start_idx = res_text.find('[')
        end_idx = res_text.rfind(']')
        if start_idx != -1 and end_idx != -1:
            res_text = res_text[start_idx:end_idx+1]
        
        parsed = json.loads(res_text)
        if type(parsed) is list and len(parsed) >= 15:
            return parsed[:15]
    except Exception as e:
        print("Lỗi từ AI trong việc sinh câu hỏi:", e)
    
    return None



# === BỘ CÂU HỎI DỰ PHÒNG TRONG CASE MẤT MẠNG HOÀN TOÀN ===
LOCAL_FALLBACK_QUESTIONS = [
    {"difficulty": "easy", "question": "Trong truyện Doraemon, Nobita sợ con gì nhất?", "answers": ["Con mèo", "Con chuột", "Con gián", "Con chó"], "correct": 2},
    {"difficulty": "easy", "question": "Hệ mặt trời có bao nhiêu hành tinh?", "answers": ["7", "8", "9", "10"], "correct": 1},
    {"difficulty": "easy", "question": "Trong cờ vua, quân nào có thể đi chéo?", "answers": ["Quân Xe", "Quân Tượng", "Quân Mã", "Quân Tốt"], "correct": 1},
    {"difficulty": "easy", "question": "Thủ đô của nước Pháp là gì?", "answers": ["London", "Berlin", "Paris", "Rome"], "correct": 2},
    {"difficulty": "easy", "question": "Loài động vật nào là biểu tượng của nước Úc?", "answers": ["Gấu Koala", "Chuột túi", "Chim cánh cụt", "Sư tử"], "correct": 1},
    {"difficulty": "medium", "question": "Đỉnh núi cao nhất thế giới Everest nằm ở dãy núi nào?", "answers": ["Andes", "Alps", "Himalaya", "Rocky"], "correct": 2},
    {"difficulty": "medium", "question": "Ai là người phát minh ra bóng đèn dây tóc?", "answers": ["Newton", "Einstein", "Thomas Edison", "Tesla"], "correct": 2},
    {"difficulty": "medium", "question": "Nguyên tố hóa học nào có ký hiệu là Au?", "answers": ["Sắt", "Bạc", "Đồng", "Vàng"], "correct": 3},
    {"difficulty": "medium", "question": "Bức họa 'Mona Lisa' là tác phẩm của ai?", "answers": ["Picasso", "Van Gogh", "Leonardo da Vinci", "Dalí"], "correct": 2},
    {"difficulty": "hard", "question": "Số Pi (π) xấp xỉ bằng bao nhiêu?", "answers": ["3.12", "3.14", "3.16", "3.18"], "correct": 1}
]

used_question_ids = set()

def fetch_and_translate_questions():
    """Kéo câu hỏi từ OpenTDB hoặc TriviaAPI rồi dịch sang Tiếng Việt."""
    global used_question_ids
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    raw_questions_list = []

    # --- LỚP 1: THỬ OPENTDB ---
    url_opentdb = 'https://opentdb.com/api.php?amount=20&type=multiple'
    for attempt in range(1, 4):
        try:
            print(f"Thử OpenTDB lần {attempt}...")
            req = urllib.request.Request(url_opentdb, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode('utf-8'))
            if data.get('response_code') == 0:
                for q in data['results']:
                    raw_questions_list.append({
                        'difficulty': q['difficulty'],
                        'question': html.unescape(q['question']),
                        'correct_answer': html.unescape(q['correct_answer']),
                        'incorrect_answers': [html.unescape(a) for a in q['incorrect_answers']]
                    })
                if len(raw_questions_list) >= 15: break
        except Exception as e:
            print(f"OpenTDB timeout/error: {e}")
            if attempt < 3: time.sleep(1)

    # --- LỚP 2: THỬ TRIVIA API (Dự phòng cực kỳ ổn định) ---
    if not raw_questions_list:
        url_trivia = 'https://the-trivia-api.com/v2/questions?limit=20'
        try:
            print("Thử Trivia API (Dự phòng cho OpenTDB)...")
            req = urllib.request.Request(url_trivia, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                for q in data:
                    raw_questions_list.append({
                        'difficulty': q['difficulty'],
                        'question': q['question']['text'],
                        'correct_answer': q['correctAnswer'],
                        'incorrect_answers': q['incorrectAnswers']
                    })
        except Exception as e:
            print(f"Trivia API lỗi: {e}")

    if not raw_questions_list: return None

    # Lọc 15 câu
    chosen = random.sample(raw_questions_list, min(20, len(raw_questions_list)))
    
    to_translate = []
    for q in chosen:
        all_ans = q['incorrect_answers'] + [q['correct_answer']]
        random.shuffle(all_ans)
        to_translate.append({
            'difficulty': q['difficulty'], 
            'question_en': q['question'], 
            'answers_en': all_ans, 
            'correct': all_ans.index(q['correct_answer'])
        })
    
    if len(to_translate) < 5: return None

    # Dịch qua AI
    items_json = json.dumps([{'difficulty': q['difficulty'], 'question': q['question_en'], 'answers': q['answers_en']} 
                             for q in to_translate[:15]], ensure_ascii=False)
    # NGUYÊN LÝ HOÀN ĐỘNG (Prompt Dịch thuật):
    # - Gom toàn bộ 15 câu vào một mảng JSON để gửi đi 1 lần duy nhất (Batch Processing). 
    # - Việc này giúp tiết kiệm thời gian chờ và giữ được cấu trúc dữ liệu đồng nhất.
    # - AI đóng vai là một chuyên gia ngôn ngữ để dịch sát nghĩa và đúng văn cảnh game.
    prompt = f"Dịch mảng JSON câu hỏi này sang Tiếng Việt chuẩn xác. Trả về mảng JSON Duy Nhất. Data: {items_json}"
    
    try:
        response = gemini_client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
        res_text = "".join([part.text for part in response.candidates[0].content.parts if part.text or ""])
        start, end = res_text.find('['), res_text.rfind(']')
        translated = json.loads(res_text[start:end+1])
        
        final = []
        for i, item in enumerate(translated):
            final.append({
                'difficulty': item['difficulty'],
                'question': item['question'],
                'answers': item['answers'],
                'correct': to_translate[i]['correct']
            })
        return final
    except Exception as e:
        print('Lỗi dịch thuật:', e)
        return None
# === LƯU TRỮ PHIÊN CHƠI (trong bộ nhớ) ===


# Mỗi phiên chơi có 1 session_id duy nhất
# Trong thực tế, bạn sẽ dùng database (SQLite, PostgreSQL...)
sessions = {}

# ==========================================
# CÁC API ENDPOINT (đường dẫn xử lý)
# ==========================================

# === TRANG AUTH ===
@app.route('/auth')
def auth_page():
    """Trang đăng nhập / đăng ký"""
    if 'username' in session:
        return redirect('/')
    return render_template('auth.html')

# === API: Đăng ký ===
@app.route('/api/auth/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username', '').strip().lower()
    email = data.get('email', '').strip().lower() # Bắt buộc phải có email
    display_name = data.get('display_name', '').strip()
    password = data.get('password', '')

    if not username or not email or not password or not display_name:
        return jsonify({'success': False, 'error': 'Vui lòng điền đầy đủ tất cả các thông tin!'})
    
    if len(username) < 3:
        return jsonify({'success': False, 'error': 'Tên đăng nhập phải ít nhất 3 ký tự!'})
    if len(password) < 6:
        return jsonify({'success': False, 'error': 'Mật khẩu phải ít nhất 6 ký tự!'})

    conn = get_db()
    if not conn:
        return jsonify({'success': False, 'error': 'Lỗi kết nối database!'}), 500

    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            # Kiểm tra tồn tại
            cur.execute("SELECT user_id FROM users WHERE username = %s OR email = %s", (username, email))
            if cur.fetchone():
                return jsonify({'success': False, 'error': 'Tên đăng nhập hoặc email đã tồn tại!'})

            # Thêm user
            cur.execute("""
                INSERT INTO users (username, email, full_name)
                VALUES (%s, %s, %s) RETURNING user_id
            """, (username, email, display_name))
            user_id = cur.fetchone()['user_id']

            # Thêm password
            hashed = hash_password(password)
            cur.execute("""
                INSERT INTO user_passwords (user_id, password_hash)
                VALUES (%s, %s)
            """, (user_id, hashed))

            conn.commit()
            session['username'] = username
            session['user_id'] = user_id
            session['display_name'] = display_name
            return jsonify({'success': True})
    except Exception as e:
        if conn: conn.rollback()
        return jsonify({'success': False, 'error': f'Lỗi hệ thống: {str(e)}'}), 500
    finally:
        if conn: conn.close()


# === API: Quên mật khẩu - Bước 1: Gửi mã ===
@app.route('/api/auth/forgot-password', methods=['POST'])
def forgot_password():
    data = request.get_json()
    email = data.get('email', '').strip().lower()

    if not email:
        return jsonify({'success': False, 'error': 'Vui lòng nhập email!'})

    conn = get_db()
    if not conn: return jsonify({'success': False, 'error': 'Lỗi database!'}), 500
    
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            # Tìm username theo email
            cur.execute("SELECT user_id, username FROM users WHERE email = %s", (email,))
            user = cur.fetchone()
            if not user:
                return jsonify({'success': False, 'error': 'Email này chưa được đăng ký!'})
            
            # Tạo mã 6 số
            code = str(random.randint(100000, 999999))
            expires_at = datetime.now() + timedelta(minutes=15)
            
            # Lưu mã vào database
            cur.execute("""
                INSERT INTO password_reset_codes (user_id, code, expires_at)
                VALUES (%s, %s, %s)
            """, (user['user_id'], code, expires_at))
            conn.commit()
            
            # Gửi email
            if send_email_code(email, code):
                return jsonify({'success': True, 'message': 'Mã xác nhận đã được gửi tới email của bạn!'})
            else:
                return jsonify({'success': False, 'error': 'Không thể gửi email. Vui lòng kiểm tra lại cấu hình server.'})
                
    except Exception as e:
        if conn: conn.rollback()
        print(f"Lỗi forgot-password: {e}")
        return jsonify({'success': False, 'error': 'Lỗi máy chủ nội bộ!'}), 500
    finally:
        if conn: conn.close()

# === API: Quên mật khẩu - Bước 2: Xác thực & Đặt lại ===
@app.route('/api/auth/verify-reset-code', methods=['POST'])
def verify_reset_code():
    data = request.get_json()
    email = data.get('email', '').strip().lower()
    code = data.get('code', '').strip()
    new_password = data.get('new_password', '')

    if not email or not code or not new_password:
        return jsonify({'success': False, 'error': 'Vui lòng điền đầy đủ thông tin!'})

    conn = get_db()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            # Tìm user
            cur.execute("SELECT user_id FROM users WHERE email = %s", (email,))
            user = cur.fetchone()
            if not user: return jsonify({'success': False, 'error': 'Lỗi xác minh!'})
            
            # Kiểm tra mã mới nhất cho user này
            cur.execute("""
                SELECT code_id FROM password_reset_codes 
                WHERE user_id = %s AND code = %s AND is_used = FALSE AND expires_at > NOW()
                ORDER BY created_at DESC LIMIT 1
            """, (user['user_id'], code))
            
            if not cur.fetchone():
                return jsonify({'success': False, 'error': 'Mã xác nhận không đúng hoặc đã hết hạn!'})
            
            # Cập nhật mật khẩu
            new_hash = hash_password(new_password)
            cur.execute("UPDATE user_passwords SET password_hash = %s WHERE user_id = %s", (new_hash, user['user_id']))
            
            # Đánh dấu mã đã dùng
            cur.execute("UPDATE password_reset_codes SET is_used = TRUE WHERE user_id = %s AND code = %s", (user['user_id'], code))
            
            conn.commit()
            return jsonify({'success': True, 'message': 'Đổi mật khẩu thành công!'})
    except Exception as e:
        if conn: conn.rollback()
        return jsonify({'success': False, 'error': 'Lỗi hệ thống!'}), 500
    finally:
        if conn: conn.close()

# === API: Đăng nhập ===

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username', '').strip().lower()
    password = data.get('password', '')

    conn = get_db()
    if not conn:
        return jsonify({'success': False, 'error': 'Lỗi kết nối database!'}), 500

    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("""
                SELECT u.user_id, u.username, u.full_name, p.password_hash 
                FROM users u 
                JOIN user_passwords p ON u.user_id = p.user_id
                WHERE u.username = %s
            """, (username,))
            user = cur.fetchone()

            if not user:
                return jsonify({'success': False, 'error': 'Tên đăng nhập không tồn tại!'})
            
            if not check_password(password, user['password_hash']):
                return jsonify({'success': False, 'error': 'Mật khẩu không đúng!'})

            session['username'] = user['username']
            session['user_id'] = user['user_id']
            session['display_name'] = user['full_name']
            return jsonify({'success': True, 'display_name': user['full_name']})
    except Exception as e:
        return jsonify({'success': False, 'error': f'Lỗi hệ thống: {str(e)}'}), 500
    finally:
        if conn: conn.close()

# === API: Đăng xuất ===
@app.route('/api/auth/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'success': True})

# === API: Kiểm tra đăng nhập ===
@app.route('/api/auth/me', methods=['GET'])
def me():
    if 'username' in session:
        return jsonify({'logged_in': True, 'username': session['username'], 'display_name': session['display_name']})
    return jsonify({'logged_in': False})

# === TRANG CHỦ: Bảo vệ bằng login_required ===
@app.route('/')
@login_required
def index():
    """Chỉ vào được nếu đã đăng nhập"""
    return render_template('index.html')

# === API: Tạo phiên chơi mới ===
@app.route('/api/game/start', methods=['POST'])
def start_game():
    """
    Tạo phiên chơi mới khi người chơi bấm "Bắt đầu".
    Input: { "player_name": "Tên người chơi" }
    Output: { "session_id": "...", "question": {...}, ... }
    """
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'success': False, 'error': 'Bạn chưa đăng nhập!'}), 401

    conn = get_db()
    if not conn:
        return jsonify({'success': False, 'error': 'Lỗi kết nối database!'}), 500
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            wallet = get_or_create_wallet(cur, user_id)
            if wallet['game_turns'] <= 0:
                return jsonify({'success': False, 'error': 'Bạn đã hết lượt chơi! Vui lòng vào Cửa hàng để mua thêm lượt.'})
            # Giảm 1 lượt chơi
            cur.execute("""
                UPDATE user_wallets
                SET game_turns = game_turns - 1, updated_at = NOW()
                WHERE user_id = %s
            """, (user_id,))
            conn.commit()
    except Exception as e:
        if conn: conn.rollback()
        return jsonify({'success': False, 'error': f'Lỗi hệ thống ví: {str(e)}'}), 500
    finally:
        if conn: conn.close()

    # Lấy dữ liệu từ request
    data = request.get_json()
    player_name = data.get('player_name', 'Người chơi')

    # Tạo ID duy nhất cho phiên chơi
    session_id = str(uuid.uuid4())

    # Mức 1: Thử OpenTDB + Dịch AI
    game_questions = fetch_and_translate_questions()
    
    # Mức 2: Nếu mạng chậm, dùng AI sinh trực tiếp
    if not game_questions:
        print("Mạng chậm, OpenTDB không phản hồi. Chuyển sang sinh câu hỏi bằng AI...")
        game_questions = generate_questions_with_ai()
    
    # Mức 3: Nếu AI cũng lỗi (hết quota, mất mạng), dùng bộ câu hỏi Offline
    if not game_questions:
        print("Tín hiệu mạng kém, đang sử dụng bộ câu hỏi dự phòng offline...")
        game_questions = LOCAL_FALLBACK_QUESTIONS



    # Lưu phiên chơi vào bộ nhớ
    sessions[session_id] = {
        'user_id': session.get('user_id'),    # Lưu user_id để sau này ghi history
        'player_name': player_name,           # Tên người chơi
        'questions': game_questions,          # 15 câu hỏi đã chọn
        'current_question': 0,               # Câu hỏi hiện tại (0-14)
        'lifelines': {                        # Quyền trợ giúp còn không
            '5050': True,
            'phone': True,
            'audience': True
        },
        'start_time': time.time(),            # Thời điểm bắt đầu
        'total_time': 0,                      # Tổng thời gian
        'is_active': True,                    # Phiên đang hoạt động
        'prize': '0 đ'                        # Tiền thưởng hiện tại
    }

    # Lấy câu hỏi đầu tiên (ẩn đáp án đúng)
    first_q = game_questions[0].copy()
    del first_q['correct']  # Không gửi đáp án đúng cho frontend!

    # Trả về dữ liệu cho frontend
    return jsonify({
        'success': True,
        'session_id': session_id,
        'player_name': player_name,
        'question': first_q,
        'question_number': 1,
        'total_questions': 15,
        'prize_levels': PRIZE_LEVELS,
        'current_prize': '0 đ',
        'milestones': MILESTONES
    })

def record_game_result(user_id, result, score, duration, metadata=None):
    """Ghi lại kết quả ván chơi vào Postgres."""
    if not user_id: return
    conn = get_db()
    if not conn: return
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO game_history (user_id, game_mode, result, score, duration_sec, metadata)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (user_id, 'solo', result, score, duration, json.dumps(metadata) if metadata else None))
            
            # Cập nhật rankings
            cur.execute("SELECT ranking_id FROM rankings WHERE user_id = %s", (user_id,))
            if cur.fetchone():
                if result == 'win':
                    cur.execute("UPDATE rankings SET total_wins = total_wins + 1, total_score = total_score + %s WHERE user_id = %s", (score, user_id))
                else:
                    cur.execute("UPDATE rankings SET total_losses = total_losses + 1, total_score = total_score + %s WHERE user_id = %s", (score, user_id))
            else:
                 cur.execute("""
                    INSERT INTO rankings (user_id, total_wins, total_losses, total_score)
                    VALUES (%s, %s, %s, %s)
                """, (user_id, 1 if result == 'win' else 0, 1 if result == 'loss' else 0, score))
            conn.commit()
    except Exception as e:
        print(f"Lỗi khi ghi lịch sử: {e}")
        conn.rollback()
    finally:
        conn.close()



# === API: Trả lời câu hỏi ===
@app.route('/api/game/answer', methods=['POST'])
def answer_question():
    """
    Xử lý khi người chơi chọn đáp án.
    Input: { "session_id": "...", "answer": 0-3 }
    Output: { "is_correct": true/false, "correct_answer": 0-3, ... }
    """
    data = request.get_json()
    session_id = data.get('session_id')
    answer = data.get('answer')  # Index đáp án: 0=A, 1=B, 2=C, 3=D

    # Kiểm tra phiên chơi có tồn tại không
    if session_id not in sessions:
        return jsonify({'success': False, 'error': 'Phiên chơi không tồn tại'}), 404

    session = sessions[session_id]

    # Kiểm tra phiên còn hoạt động không
    if not session['is_active']:
        return jsonify({'success': False, 'error': 'Phiên chơi đã kết thúc'}), 400

    # Lấy câu hỏi hiện tại
    current = session['current_question']
    question = session['questions'][current]
    correct_answer = question['correct']

    # Kiểm tra đúng/sai
    is_correct = (answer == correct_answer)

    if is_correct:
        # === TRẢ LỜI ĐÚNG ===
        session['current_question'] += 1
        session['prize'] = PRIZE_LEVELS[current]

        # Kiểm tra đã trả lời hết 15 câu chưa
        if session['current_question'] >= 15:
            # THẮNG GAME!
            session['is_active'] = False
            session['total_time'] = int(time.time() - session['start_time'])
            
            # Ghi vào DB
            record_game_result(session.get('user_id'), 'win', 150000000, session['total_time'])

            return jsonify({
                'success': True,
                'is_correct': True,
                'correct_answer': correct_answer,
                'game_over': True,
                'won': True,
                'prize': PRIZE_LEVELS[14],
                'correct_count': 15,
                'total_time': session['total_time']
            })


        # Gửi câu hỏi tiếp theo
        next_q = session['questions'][session['current_question']].copy()
        del next_q['correct']  # Ẩn đáp án đúng

        return jsonify({
            'success': True,
            'is_correct': True,
            'correct_answer': correct_answer,
            'game_over': False,
            'next_question': next_q,
            'question_number': session['current_question'] + 1,
            'current_prize': session['prize']
        })
    else:
        # === TRẢ LỜI SAI ===
        session['is_active'] = False
        session['total_time'] = int(time.time() - session['start_time'])

        # Tính tiền dựa trên mốc an toàn
        safe_prize = '0 đ'
        score = 0
        for milestone in MILESTONES:
            if current > milestone:
                safe_prize = PRIZE_LEVELS[milestone]
                # Parse số tiền (ví dụ "2.000.000 đ" -> 2000000)
                score = int(safe_prize.replace('.', '').replace(' đ', ''))

        # Ghi vào DB
        record_game_result(session.get('user_id'), 'loss', score, session['total_time'])

        return jsonify({
            'success': True,
            'is_correct': False,
            'correct_answer': correct_answer,
            'game_over': True,
            'won': False,
            'prize': safe_prize,
            'correct_count': current,
            'total_time': session['total_time']
        })



# === API: Sử dụng quyền trợ giúp ===
@app.route('/api/game/lifeline', methods=['POST'])
def use_lifeline():
    """
    Xử lý khi người chơi dùng quyền trợ giúp.
    Input: { "session_id": "...", "type": "5050" | "phone" | "audience" }
    """
    data = request.get_json()
    session_id = data.get('session_id')
    lifeline_type = data.get('type')

    # Kiểm tra phiên
    if session_id not in sessions:
        return jsonify({'success': False, 'error': 'Phiên không tồn tại'}), 404

    session = sessions[session_id]

    # Kiểm tra quyền trợ giúp còn không
    if not session['lifelines'].get(lifeline_type, False):
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'success': False, 'error': 'Bạn chưa đăng nhập!'}), 401
        
        conn = get_db()
        if not conn:
            return jsonify({'success': False, 'error': 'Lỗi kết nối database!'}), 500
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                wallet = get_or_create_wallet(cur, user_id)
                if wallet['bonus_lifelines'] <= 0:
                    return jsonify({'success': False, 'error': 'Quyền trợ giúp đã hết và bạn không còn lượt trợ giúp dự phòng!'})
                # Trừ 1 lượt trợ giúp trong ví
                cur.execute("""
                    UPDATE user_wallets
                    SET bonus_lifelines = bonus_lifelines - 1, updated_at = NOW()
                    WHERE user_id = %s
                """, (user_id,))
                conn.commit()
        except Exception as e:
            if conn: conn.rollback()
            return jsonify({'success': False, 'error': f'Lỗi hệ thống ví: {str(e)}'}), 500
        finally:
            if conn: conn.close()
    else:
        # Đánh dấu đã dùng
        session['lifelines'][lifeline_type] = False

    # Lấy câu hỏi hiện tại
    question = session['questions'][session['current_question']]
    correct = question['correct']

    # === XỬ LÝ TỪNG LOẠI TRỢ GIÚP ===
    if lifeline_type == '5050':
        # 50:50: Loại 2 đáp án sai, giữ lại đáp án đúng + 1 sai
        wrong_indices = [i for i in range(4) if i != correct]
        random.shuffle(wrong_indices)
        removed = wrong_indices[:2]  # Loại 2 đáp án sai

        return jsonify({
            'success': True,
            'type': '5050',
            'removed': removed  # Danh sách index bị loại
        })

    elif lifeline_type == 'phone':
        # Gọi điện: 70% gợi ý đúng, 30% gợi ý sai
        is_right = random.random() < 0.7
        if is_right:
            suggestion = correct
            confidence = random.randint(70, 95)
        else:
            wrong = [i for i in range(4) if i != correct]
            suggestion = random.choice(wrong)
            confidence = random.randint(30, 60)

        return jsonify({
            'success': True,
            'type': 'phone',
            'suggestion': suggestion,      # Index đáp án gợi ý
            'confidence': confidence        # Phần trăm tự tin
        })

    elif lifeline_type == 'audience':
        # Hỏi khán giả: Tạo phân bố % ngẫu nhiên
        percents = [0, 0, 0, 0]
        # Đáp án đúng có % cao nhất
        percents[correct] = random.randint(35, 70)
        remaining = 100 - percents[correct]

        # Chia phần còn lại cho 3 đáp án sai
        for i in range(4):
            if i == correct:
                continue
            if remaining <= 0:
                percents[i] = 0
            else:
                p = random.randint(0, remaining)
                percents[i] = p
                remaining -= p

        # Đảm bảo tổng = 100
        diff = 100 - sum(percents)
        percents[correct] += diff

        return jsonify({
            'success': True,
            'type': 'audience',
            'percents': percents  # [%A, %B, %C, %D]
        })

    return jsonify({'success': False, 'error': 'Loại trợ giúp không hợp lệ'}), 400


# === API: Dừng cuộc chơi ===
@app.route('/api/game/stop', methods=['POST'])
def stop_game():
    """Xử lý khi người chơi quyết định dừng cuộc chơi."""
    data = request.get_json()
    session_id = data.get('session_id')

    if session_id not in sessions:
        return jsonify({'success': False, 'error': 'Phiên không tồn tại'}), 404

    session = sessions[session_id]
    session['is_active'] = False
    session['total_time'] = int(time.time() - session['start_time'])

    current = session['current_question']
    prize = PRIZE_LEVELS[current - 1] if current > 0 else '0 đ'

    # Ghi vào DB
    score = int(prize.replace('.', '').replace(' đ', '')) if (prize != '0 đ') else 0
    record_game_result(session.get('user_id'), 'loss', score, session['total_time'])

    return jsonify({
        'success': True,
        'prize': prize,
        'correct_count': current,
        'total_time': session['total_time']
    })


# === API: Hết giờ ===
@app.route('/api/game/timeout', methods=['POST'])
def timeout():
    """Xử lý khi người chơi hết thời gian trả lời."""
    data = request.get_json()
    session_id = data.get('session_id')

    if session_id not in sessions:
        return jsonify({'success': False, 'error': 'Phiên không tồn tại'}), 404

    session = sessions[session_id]
    session['is_active'] = False
    session['total_time'] = int(time.time() - session['start_time'])

    current = session['current_question']
    correct = session['questions'][current]['correct']

    # Tính tiền theo mốc an toàn
    safe_prize = '0 đ'
    for milestone in MILESTONES:
        if current > milestone:
            safe_prize = PRIZE_LEVELS[milestone]

    # Ghi vào DB
    score = int(safe_prize.replace('.', '').replace(' đ', '')) if (safe_prize != '0 đ') else 0
    record_game_result(session.get('user_id'), 'loss', score, session['total_time'])

    return jsonify({
        'success': True,
        'correct_answer': correct,
        'prize': safe_prize,
        'correct_count': current,
        'total_time': session['total_time']
    })


# === API: CHATBOT ===
@app.route('/api/chatbot', methods=['POST'])
def chatbot():
    """
    Xử lý tin nhắn chatbot bằng Gemini AI.
    Input: { "message": "...", "session_id": "..." }
    Output: { "reply": "..." }
    """
    data = request.get_json()
    message = data.get('message', '')
    session_id = data.get('session_id', '')

    # Lấy thông tin phiên chơi (nếu có)
    session = sessions.get(session_id, {})
    player_name = session.get('player_name', 'bạn')
    current = session.get('current_question', 0)
    
    if not gemini_client:
        return jsonify({'success': True, 'reply': "⚠️ Lỗi: Chưa cấu hình GEMINI_API_KEY trong file .env hoặc hệ thống nên chatbot đang bị vô hiệu hóa."})

    try:
        # Xây dựng prompt cung cấp ngữ cảnh trò chơi cho Gemini đóng vai
        # NGUYÊN LÝ HOÀN ĐỘNG (Prompt Chatbot):
        # 1. Cung cấp Context (Ngữ cảnh): Đưa tên người chơi và vị trí câu hiện tại vào để AI trả lời cá nhân hóa.
        # 2. Thiết lập Nhân cách (Persona): Đóng vai MC vui vẻ, thân thiện, động viên.
        # 3. Ràng buộc Logic (Constraints): Tuyệt đối KHÔNG lộ đáp án (để game luôn công bằng).
        # 4. Điều tiết độ dài: Yêu cầu trả lời ngắn gọn (< 3 câu) để giao diện chat không bị tràn.
        prompt = f'''Bạn là MC Trợ Lý ảo của trò chơi "Ai Là Triệu Phú". 
Tên người chơi là: {player_name}. Người chơi đang ở câu hỏi số {current + 1}/15.
Luật trò chơi: Có 15 câu hỏi, 3 quyền trợ giúp (50:50, Gọi ĐT, Hỏi khán giả), 2 mốc an toàn ở câu 5 và câu 10.

Câu hỏi/tin nhắn của người chơi: "{message}"

Nhiệm vụ: Trả lời người chơi bằng giọng điệu vui vẻ, tự nhiên, thân thiện và động viên họ. 
QUAN TRỌNG: KHÔNG ĐƯỢC để lộ đáp án đúng của bất kỳ câu hỏi nào nếu họ yêu cầu gợi ý (hãy khuyên họ dùng quyền trợ giúp).
Hãy trả lời ngắn gọn, súc tích (dưới 3 câu).'''

        # Gọi Gemini API để sinh câu trả lời
        response = gemini_client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
        )
        reply = response.text

    except Exception as e:
        print('Lỗi Gemini chatbot:', e)
        reply = f'Xin lỗi, tôi đang gặp trục trặc hệ thống. Vui lòng thử lại!'

    return jsonify({'success': True, 'reply': reply})


# === API: DỊCH CÂU HỎI (MỚI) ===
@app.route('/api/translate', methods=['POST'])
def translate_question():
    """
    Dịch câu hỏi hiện tại sang ngôn ngữ khác bằng Gemini API.
    Input: { "session_id": "...", "target_lang": "English" }
    Output: { "translated": { "question": "...", "answers": [...] } }
    """
    data = request.get_json()
    session_id = data.get('session_id')
    target_lang = data.get('target_lang', 'Tiếng Anh')
    
    if session_id not in sessions:
        return jsonify({'success': False, 'error': 'Phiên chơi không tồn tại'}), 404
        
    session = sessions[session_id]
    current = session['current_question']
    question = session['questions'][current]
    
    if not gemini_client:
         return jsonify({'success': False, 'error': 'Chưa cấu hình GEMINI_API_KEY'}), 500

    q_text = question['question']
    ans_texts = ', '.join(f"{chr(65+i)}: {ans}" for i, ans in enumerate(question['answers']))
    
    # Prompt yêu cầu AI trả về chuẩn JSON đã dịch
    prompt = f'''Dịch câu hỏi trắc nghiệm dưới đây sang {target_lang}.
Câu hỏi: {q_text}
Các đáp án: {ans_texts}
Trả về kết quả 100% dưới dạng chuỗi JSON nguyên gốc, KHÔNG BỌC trong markdown (chỉ format: {{"question": "câu hỏi đã dịch", "answers": ["dịch A", "dịch B", "dịch C", "dịch D"]}}), không thêm bất kỳ chữ nào khác.'''

    try:
        response = gemini_client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
        )
        res_text = response.text.strip()

        
        # Parse chuỗi JSON trả về
        if res_text.startswith("```json"): 
            res_text = res_text[7:]
        if res_text.startswith("```"):
            res_text = res_text[3:]
        if res_text.endswith("```"): 
            res_text = res_text[:-3]
            
        translated_data = json.loads(res_text.strip())
        return jsonify({'success': True, 'translated': translated_data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


def process_chatbot_message(msg, name, current_q):
    """
    Xử lý logic chatbot - phân tích tin nhắn và trả lời phù hợp.
    msg: nội dung tin nhắn (đã lowercase)
    name: tên người chơi
    current_q: câu hỏi hiện tại (0-14)
    """

    # --- Chào hỏi ---
    if any(w in msg for w in ['xin chào', 'hello', 'hi', 'chào', 'hey']):
        return f"Chào {name}! 😊 Tôi là MC Trợ Lý, sẵn sàng hỗ trợ bạn trong suốt trò chơi!"

    # --- Hỏi luật chơi ---
    if any(w in msg for w in ['luật', 'cách chơi', 'hướng dẫn', 'quy tắc', 'rules']):
        return ("📋 Luật chơi:\n"
                "• 15 câu hỏi từ dễ đến khó\n"
                "• Mỗi câu 30 giây suy nghĩ\n"
                "• 3 quyền trợ giúp: 50:50, Gọi ĐT, Hỏi khán giả\n"
                "• 2 mốc an toàn: Câu 5 (2 triệu) và Câu 10 (22 triệu)\n"
                "• Trả lời sai → nhận tiền mốc an toàn gần nhất")

    # --- Hỏi về trợ giúp ---
    if any(w in msg for w in ['trợ giúp', '50:50', 'gọi', 'khán giả', 'lifeline']):
        return ("🆘 3 Quyền trợ giúp:\n"
                "• ✂️ 50:50: Loại bỏ 2 đáp án sai\n"
                "• 📞 Gọi điện: Hỏi ý kiến người thân (70% chính xác)\n"
                "• 👥 Khán giả: Xem bình chọn của khán giả\n"
                "Mỗi quyền chỉ dùng được 1 lần!")

    # --- Hỏi tiền thưởng / tiến độ ---
    if any(w in msg for w in ['tiền', 'thưởng', 'giải', 'bao nhiêu', 'prize']):
        if current_q > 0:
            return f"💰 Bạn đang ở câu {current_q + 1}/15. Tiền hiện tại: {PRIZE_LEVELS[current_q - 1]}"
        return "💰 Bạn đang ở câu 1/15. Hãy trả lời đúng để nhận thưởng!"

    # --- Xin gợi ý ---
    if any(w in msg for w in ['gợi ý', 'hint', 'mách', 'đáp án', 'answer']):
        return "🤔 Tôi không thể cho đáp án trực tiếp! Nhưng hãy dùng quyền trợ giúp nếu không chắc. Tin vào trực giác nhé!"

    # --- Hỏi dừng cuộc chơi ---
    if any(w in msg for w in ['dừng', 'bỏ cuộc', 'stop', 'quit']):
        return "🤚 Nếu không chắc chắn, dừng lại là quyết định khôn ngoan! Nhấn nút 'Dừng cuộc chơi' bên phải."

    # --- Giới thiệu bản thân ---
    if any(w in msg for w in ['bạn là ai', 'tên gì', 'who are you']):
        return "🤖 Tôi là MC Trợ Lý - chatbot AI hỗ trợ bạn trong game Ai Là Triệu Phú! Hỏi tôi bất cứ điều gì!"

    # --- Cảm ơn ---
    if any(w in msg for w in ['cảm ơn', 'thanks', 'thank', 'tks']):
        return "🙏 Không có gì! Chúc bạn may mắn và mang về giải thưởng lớn! 💪"

    # --- Lo lắng / căng thẳng ---
    if any(w in msg for w in ['khó', 'căng', 'sợ', 'lo', 'nervous']):
        tips = [
            "😌 Bình tĩnh! Đọc kỹ câu hỏi, loại trừ đáp án sai, tin vào trực giác. Bạn làm được! 💪",
            "🧘 Hít thở sâu! Hãy nhớ bạn vẫn còn quyền trợ giúp. Đừng vội vàng!",
            "💡 Mẹo: Loại bỏ những đáp án chắc chắn sai trước, rồi chọn giữa các đáp án còn lại."
        ]
        return random.choice(tips)

    # --- Vui vẻ ---
    if any(w in msg for w in ['vui', 'hay', 'thích', 'good', 'great']):
        return "🎉 Tuyệt vời! Tiếp tục chiến đấu nhé! Mỗi câu đúng đưa bạn gần giải thưởng lớn hơn! 🏆"

    # --- Chiến lược ---
    if any(w in msg for w in ['chiến lược', 'mẹo', 'tips', 'strategy']):
        return ("🎯 Chiến lược hay:\n"
                "1. Câu dễ → trả lời nhanh, tiết kiệm trợ giúp\n"
                "2. Câu khó → dùng 50:50 trước, rồi suy luận\n"
                "3. Gần mốc an toàn → cố gắng vượt qua\n"
                "4. Không chắc chắn → dừng cuộc chơi là khôn ngoan!")

    # --- PWA / App ---
    if any(w in msg for w in ['app', 'cài', 'điện thoại', 'mobile', 'install']):
        return ("📱 Cài app trên điện thoại:\n"
                "• iPhone: Mở Safari → Nhấn nút Chia sẻ → 'Thêm vào MH chính'\n"
                "• Android: Mở Chrome → Nhấn menu ⋮ → 'Cài ứng dụng'")

    # --- Mặc định ---
    defaults = [
        f"Hỏi tôi về luật chơi, trợ giúp, chiến lược, hoặc bất cứ thắc mắc nào nhé {name}! 😊",
        "Tôi có thể giúp bạn hiểu luật chơi, quyền trợ giúp, và chiến lược! 🎯",
        "Hãy tập trung vào câu hỏi! Nếu cần hỗ trợ, cứ hỏi tôi nhé! 💡",
        f"Bạn đang làm rất tốt {name}! Tiếp tục cố gắng! 🌟"
    ]
    return random.choice(defaults)


# === API: Lịch sử chơi của tôi ===
@app.route('/api/game/history', methods=['GET'])
@login_required
def get_user_history():
    user_id = session.get('user_id')
    conn = get_db()
    if not conn:
        return jsonify({'success': False, 'error': 'Database error'}), 500
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("""
                SELECT history_id, result, score, duration_sec, played_at 
                FROM game_history 
                WHERE user_id = %s 
                ORDER BY played_at DESC 
                LIMIT 20
            """, (user_id,))
            rows = cur.fetchall()
            history = [dict(row) for row in rows]
            return jsonify({'success': True, 'history': history})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        conn.close()

# === API: Bảng xếp hạng (DATABASE) ===
@app.route('/api/leaderboard', methods=['GET'])
def get_leaderboard():
    """Lấy bảng xếp hạng top 10 từ database."""
    conn = get_db()
    if not conn:
        return jsonify({'success': False, 'error': 'Database error'}), 500
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("""
                SELECT u.full_name as player_name, r.total_score as score, r.total_wins as wins
                FROM rankings r
                JOIN users u ON r.user_id = u.user_id
                ORDER BY r.total_score DESC
                LIMIT 10
            """)
            rows = cur.fetchall()
            return jsonify({'success': True, 'leaderboard': [dict(row) for row in rows]})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        conn.close()

# (Route add_to_leaderboard cũ có thể xóa vì đã có record_game_result ghi trực tiếp)



# === PHỤC VỤ FILE PWA ===
@app.route('/manifest.json')
def manifest():
    """Trả về manifest cho PWA (Progressive Web App)."""
    return send_from_directory('static', 'manifest.json')

@app.route('/sw.js')
def service_worker():
    """Trả về Service Worker cho PWA."""
    return send_from_directory('static', 'sw.js')

# ==========================================
# CÁC API CỬA HÀNG (SHOP API)
# ==========================================

# === API: LẤY THÔNG TIN VÍ ===
@app.route('/api/shop/wallet', methods=['GET'])
@login_required
def get_shop_wallet():
    user_id = session.get('user_id')
    conn = get_db()
    if not conn:
        return jsonify({'success': False, 'error': 'Lỗi kết nối database!'}), 500
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            wallet = get_or_create_wallet(cur, user_id)
            conn.commit()
            return jsonify({
                'success': True,
                'game_turns': wallet['game_turns'],
                'bonus_lifelines': wallet['bonus_lifelines']
            })
    except Exception as e:
        if conn: conn.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if conn: conn.close()

# === API: LỊCH SỬ MUA HÀNG ===
@app.route('/api/shop/history', methods=['GET'])
@login_required
def get_shop_history():
    user_id = session.get('user_id')
    conn = get_db()
    if not conn:
        return jsonify({'success': False, 'error': 'Lỗi kết nối database!'}), 500
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("""
                SELECT item_type, quantity, total_price, payment_ref, status, created_at
                FROM shop_transactions
                WHERE user_id = %s
                ORDER BY created_at DESC
                LIMIT 20
            """, (user_id,))
            rows = cur.fetchall()
            txns = []
            for r in rows:
                txn = dict(r)
                # Chuyển đổi datetime sang định dạng ISO cho JSON
                if txn.get('created_at'):
                    txn['created_at'] = txn['created_at'].isoformat()
                txns.append(txn)
            return jsonify({'success': True, 'transactions': txns})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if conn: conn.close()

# === API: TẠO ĐƠN HÀNG MỚI ===
@app.route('/api/shop/create-order', methods=['POST'])
@login_required
def create_shop_order():
    data = request.get_json()
    item_type = data.get('item_type') # 'game_turn' hoặc 'bonus_lifeline'
    quantity = data.get('quantity')

    if item_type not in ['game_turn', 'bonus_lifeline'] or not isinstance(quantity, int) or quantity <= 0:
        return jsonify({'success': False, 'error': 'Dữ liệu không hợp lệ!'}), 400

    prices = {'game_turn': 5000, 'bonus_lifeline': 2000}
    total_price = prices[item_type] * quantity
    user_id = session.get('user_id')

    # Tạo mã thanh toán ngẫu nhiên
    payment_ref = f"AMT_{int(time.time())}_{uuid.uuid4().hex[:6].upper()}"

    conn = get_db()
    if not conn:
        return jsonify({'success': False, 'error': 'Lỗi kết nối database!'}), 500
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("""
                INSERT INTO shop_transactions (user_id, item_type, quantity, total_price, payment_ref, status)
                VALUES (%s, %s, %s, %s, %s, 'pending')
            """, (user_id, item_type, quantity, total_price, payment_ref))
            conn.commit()
            # Tạo URL QR SePay (dùng VietQR — SePay hỗ trợ chuẩn này)
            qr_url = (
                f"https://img.vietqr.io/image/{SEPAY_BANK_CODE}-{SEPAY_ACCOUNT_NO}-compact2.png"
                f"?amount={total_price}&addInfo={urllib.parse.quote(payment_ref)}"
                f"&accountName={urllib.parse.quote(SEPAY_ACCOUNT_NAME)}"
            )
            return jsonify({
                'success': True,
                'txn_id': payment_ref,   # dùng payment_ref làm ID đơn
                'payment_ref': payment_ref,
                'total_price': total_price,
                'qr_url': qr_url,
                'bank_code': SEPAY_BANK_CODE,
                'account_no': SEPAY_ACCOUNT_NO,
                'account_name': SEPAY_ACCOUNT_NAME,
            })
    except Exception as e:
        if conn: conn.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if conn: conn.close()

# === API: KIỂM TRA TRẠNG THÁI ĐƠN HÀNG (POLLING) ===
@app.route('/api/shop/check-status', methods=['GET'])
@login_required
def check_order_status():
    payment_ref = request.args.get('ref')
    if not payment_ref:
        return jsonify({'success': False, 'error': 'Thiếu payment_ref'}), 400
    conn = get_db()
    if not conn:
        return jsonify({'success': False, 'error': 'Lỗi kết nối database!'}), 500
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                "SELECT status FROM shop_transactions WHERE payment_ref = %s",
                (payment_ref,)
            )
            row = cur.fetchone()
            if not row:
                return jsonify({'success': False, 'error': 'Không tìm thấy giao dịch'}), 404
            return jsonify({'success': True, 'status': row['status']})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if conn: conn.close()

# === API: WEBHOOK XỬ LÝ THANH TOÁN ===
@app.route('/api/shop/webhook', methods=['POST'])
@app.route('/api/webhook/sepay', methods=['POST'])
def shop_webhook():
    import hmac
    import hashlib
    import re

    data = request.get_json() or {}
    
    # Hàm hỗ trợ xác thực Webhook SePay
    def verify_sepay_request():
        webhook_secret = os.environ.get('WEBHOOK_SECRET', 'dev-secret-123')
        if not webhook_secret:
            return False
        
        # 1. Xác thực bằng X-SePay-Signature header
        received_sig = request.headers.get('X-SePay-Signature')
        if received_sig:
            raw_body = request.get_data()
            computed_sig = hmac.new(
                webhook_secret.encode('utf-8'),
                raw_body,
                hashlib.sha256
            ).hexdigest()
            if hmac.compare_digest(computed_sig, received_sig):
                return True
                
        # 2. Xác thực bằng Authorization: Apikey <secret> hoặc Bearer <secret>
        auth_header = request.headers.get('Authorization')
        if auth_header:
            parts = auth_header.split(' ')
            if len(parts) == 2 and parts[0].lower() in ['apikey', 'bearer']:
                if hmac.compare_digest(parts[1], webhook_secret):
                    return True
                    
        # 3. Xác thực bằng X-API-Key hoặc X-Secret-Key
        api_key = request.headers.get('X-API-Key') or request.headers.get('X-Secret-Key')
        if api_key:
            if hmac.compare_digest(api_key, webhook_secret):
                return True
                
        return False

    # Phân loại luồng Webhook dựa trên cấu trúc payload
    is_legacy = False
    legacy_user_id = None
    legacy_item_type = None

    if 'content' in data:
        # Luồng 1: Webhook SePay chuẩn (Chuyển khoản QR ngân hàng thật hoặc chạy test_webhook.py)
        is_local = request.remote_addr in ['127.0.0.1', 'localhost']
        is_authenticated = verify_sepay_request()
        if not is_authenticated and not is_local:
            return jsonify({'success': False, 'error': 'Xác thực Webhook SePay thất bại!'}), 401

        content = data.get('content', '').strip()
        
        # Hỗ trợ phản hồi thành công cho chức năng "Gửi thử" (Test Webhook) của SePay
        if 'sepay test' in content.lower() or data.get('code') == 'SEPAYTEST':
            return jsonify({'success': True, 'message': 'Kết nối webhook thành công! (Test Webhook)'}), 200

        sepay_txn_id = data.get('id')
        try:
            transfer_amount = int(data.get('transferAmount', 0))
        except (ValueError, TypeError):
            transfer_amount = 0

        # 1.1 Kiểm tra xem có phải định dạng đơn hàng AMT_...
        # Hỗ trợ cả trường hợp có hoặc không có dấu gạch dưới '_' do ngân hàng lọc bỏ ký tự đặc biệt
        match_amt = re.search(r'AMT_?(\d+)_?([A-Z0-9]{6})', content, re.IGNORECASE)
        if match_amt:
            payment_ref = f"AMT_{match_amt.group(1)}_{match_amt.group(2).upper()}"
            status = 'paid'
        else:
            # 1.2 Kiểm tra xem có phải định dạng legacy ML/MT <user_id> (từ test_webhook.py)
            match_legacy = re.search(r'^(ML|MT)\s*(\d+)$', content, re.IGNORECASE)
            if match_legacy:
                type_prefix = match_legacy.group(1).upper()
                legacy_user_id = int(match_legacy.group(2))
                legacy_item_type = 'game_turn' if type_prefix == 'ML' else 'bonus_lifeline'
                is_legacy = True
                payment_ref = f"AMT_LEGACY_{sepay_txn_id}"
                status = 'paid'
            else:
                return jsonify({'success': False, 'error': 'Nội dung chuyển khoản không chứa mã đơn hàng hợp lệ!'}), 400
    else:
        # Luồng 2: Webhook Giả lập từ Frontend/Giao diện DEV (chữ ký ref:status)
        payment_ref = data.get('payment_ref')
        status = data.get('status')
        signature = data.get('signature')

        if not payment_ref or not status or not signature:
            return jsonify({'success': False, 'error': 'Thiếu tham số bắt buộc!'}), 400

        # Xác minh chữ ký SHA256 HMAC cho luồng giả lập
        webhook_secret = os.environ.get('WEBHOOK_SECRET', 'dev-secret-123').encode('utf-8')
        msg = f"{payment_ref}:{status}".encode('utf-8')
        expected_sig = hmac.new(webhook_secret, msg, hashlib.sha256).hexdigest()

        if not hmac.compare_digest(expected_sig, signature):
            # Thử phương án dự phòng sử dụng 'dev-secret-123' cho môi trường phát triển
            fallback_sig = hmac.new(b'dev-secret-123', msg, hashlib.sha256).hexdigest()
            if not hmac.compare_digest(fallback_sig, signature):
                return jsonify({'success': False, 'error': 'Chữ ký không hợp lệ!'}), 403
        
        transfer_amount = None

    conn = get_db()
    if not conn:
        return jsonify({'success': False, 'error': 'Lỗi kết nối database!'}), 500
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            if is_legacy:
                # Xử lý đặc biệt cho luồng legacy để tạo đơn tự động nếu chưa có
                cur.execute("""
                    SELECT user_id, item_type, quantity, total_price, status
                    FROM shop_transactions
                    WHERE payment_ref = %s
                """, (payment_ref,))
                txn = cur.fetchone()
                if not txn:
                    prices = {'game_turn': 5000, 'bonus_lifeline': 2000}
                    quantity = transfer_amount // prices[legacy_item_type]
                    if quantity <= 0:
                        return jsonify({'success': False, 'error': 'Số tiền không đủ để mua lượt!'}), 400
                    
                    cur.execute("""
                        INSERT INTO shop_transactions (user_id, item_type, quantity, total_price, payment_ref, status)
                        VALUES (%s, %s, %s, %s, %s, 'pending')
                        RETURNING user_id, item_type, quantity, total_price, status
                    """, (legacy_user_id, legacy_item_type, quantity, transfer_amount, payment_ref))
                    txn = cur.fetchone()
            else:
                # Chỉ lấy các trường cần thiết để tương thích hoàn hảo với mọi cấu trúc cột khóa chính
                cur.execute("""
                    SELECT user_id, item_type, quantity, total_price, status
                    FROM shop_transactions
                    WHERE payment_ref = %s
                """, (payment_ref,))
                txn = cur.fetchone()
            
            if not txn:
                return jsonify({'success': False, 'error': 'Giao dịch không tồn tại!'}), 404

            if txn['status'] == 'paid':
                return jsonify({'success': True, 'message': 'Giao dịch đã được thanh toán rồi!'})

            # Kiểm tra số tiền chuyển khoản của SePay thật (nếu có)
            if transfer_amount is not None and not is_legacy and transfer_amount < txn['total_price']:
                return jsonify({'success': False, 'error': f"Số tiền không khớp! Cần {txn['total_price']} đ nhưng nhận được {transfer_amount} đ"}), 400

            if status == 'paid':
                # Cập nhật trạng thái
                cur.execute("""
                    UPDATE shop_transactions
                    SET status = 'paid'
                    WHERE payment_ref = %s
                """, (payment_ref,))

                # Đảm bảo người dùng có ví
                get_or_create_wallet(cur, txn['user_id'])

                # Cộng số lượng vật phẩm vào ví mới (user_wallets)
                if txn['item_type'] == 'game_turn':
                    cur.execute("""
                        UPDATE user_wallets
                        SET game_turns = game_turns + %s, updated_at = NOW()
                        WHERE user_id = %s
                    """, (txn['quantity'], txn['user_id']))
                elif txn['item_type'] == 'bonus_lifeline':
                    cur.execute("""
                        UPDATE user_wallets
                        SET bonus_lifelines = bonus_lifelines + %s, updated_at = NOW()
                        WHERE user_id = %s
                    """, (txn['quantity'], txn['user_id']))

                # Đồng thời cập nhật thêm bảng users cũ để đảm bảo tương thích 100% với test_webhook.py
                try:
                    if txn['item_type'] == 'game_turn':
                        cur.execute("UPDATE users SET plays_left = plays_left + %s WHERE user_id = %s", (txn['quantity'], txn['user_id']))
                    elif txn['item_type'] == 'bonus_lifeline':
                        cur.execute("UPDATE users SET extra_lifelines = extra_lifelines + %s WHERE user_id = %s", (txn['quantity'], txn['user_id']))
                except Exception as e:
                    # Bỏ qua nếu cột không tồn tại
                    pass
                
                conn.commit()
                return jsonify({'success': True, 'message': 'Cộng vật phẩm thành công!'})
            else:
                cur.execute("""
                    UPDATE shop_transactions
                    SET status = %s
                    WHERE payment_ref = %s
                """, (status, payment_ref))
                conn.commit()
                return jsonify({'success': True, 'message': f'Giao dịch được cập nhật thành {status}'})
    except Exception as e:
        if conn: conn.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if conn: conn.close()


# === CHẠY SERVER ===
if __name__ == '__main__':
    print("=" * 50)
    print("🎮 AI LÀ TRIỆU PHÚ - SERVER")
    print("=" * 50)
    print("🌐 Web:  http://localhost:5001")
    print("📱 App:  Mở link trên bằng điện thoại để cài PWA")
    print("=" * 50)

    # host='0.0.0.0' = cho phép truy cập từ thiết bị khác trong cùng mạng WiFi
    # debug=True = tự động reload khi sửa code
    
    # Khởi tạo database nếu chưa có table
    with app.app_context():
        conn = get_connection()
        if conn:
            create_schema(conn)
            conn.close()

    app.run(host='0.0.0.0', port=5001, debug=True)

