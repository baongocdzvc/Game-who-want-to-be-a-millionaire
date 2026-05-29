/* ==========================================
   AI LÀ TRIỆU PHÚ - FRONTEND (gọi Backend API)
   File: game.js
   Mô tả: Giao diện gọi API từ Python Flask server
   ========================================== */

// === URL CỦA SERVER BACKEND ===
// Khi chạy cùng server Flask, dùng đường dẫn tương đối
const API_URL = '';

// === CÁC MỨC TIỀN THƯỞNG (15 mức) ===
const PRIZE_LEVELS = [
    "200.000 đ", "400.000 đ", "600.000 đ", "1.000.000 đ", "2.000.000 đ",
    "3.000.000 đ", "6.000.000 đ", "10.000.000 đ", "14.000.000 đ", "22.000.000 đ",
    "30.000.000 đ", "40.000.000 đ", "60.000.000 đ", "85.000.000 đ", "150.000.000 đ"
];
const MILESTONES = [4, 9]; // Mốc an toàn

// === BIẾN TRẠNG THÁI ===
let sessionId = '';           // ID phiên chơi từ server
let playerName = '';          // Tên người chơi
let currentQuestion = 0;      // Câu đang chơi
let timer = null;             // Bộ đếm giờ
let timeLeft = 30;            // Giây còn lại
let isAnswered = false;       // Đã trả lời chưa
let soundEnabled = true;      // Âm thanh bật/tắt
let chatbotOpen = false;      // Chatbot mở/đóng

// === KHỞI TẠO KHI TRANG TẢI XONG ===
document.addEventListener('DOMContentLoaded', () => {
    createParticles();
    buildMoneyLadder();
    addBotMessage("Xin chào! 👋 Tôi là MC Trợ Lý. Chúc bạn may mắn nhé!");
    // registerServiceWorker(); // Tắt SW để tránh loop
});


// === ĐĂNG KÝ SERVICE WORKER (cho PWA) ===
function registerServiceWorker() {
    if ('serviceWorker' in navigator) {
        navigator.serviceWorker.register('/sw.js')
            .then(() => console.log('✅ PWA Service Worker đã đăng ký'))
            .catch(err => console.log('SW lỗi:', err));
    }
}

// === TẠO HIỆU ỨNG HẠT BAY ===
function createParticles() {
    const c = document.getElementById('particles');
    for (let i = 0; i < 30; i++) {
        const p = document.createElement('div');
        p.className = 'particle';
        p.style.left = Math.random() * 100 + '%';
        p.style.top = Math.random() * 100 + '%';
        p.style.animationDelay = Math.random() * 6 + 's';
        p.style.animationDuration = (4 + Math.random() * 4) + 's';
        c.appendChild(p);
    }
}

// === XÂY BẢNG TIỀN THƯỞNG ===
function buildMoneyLadder() {
    const list = document.getElementById('money-list');
    list.innerHTML = '';
    PRIZE_LEVELS.forEach((prize, i) => {
        const li = document.createElement('li');
        li.id = 'level-' + i;
        if (MILESTONES.includes(i)) li.classList.add('milestone');
        li.innerHTML = `<span class="level-num">${i + 1}</span><span>${prize}</span>`;
        list.appendChild(li);
    });
}

// === BẮT ĐẦU GAME - GỌI API /api/game/start ===
async function startGame() {
    playerName = document.getElementById('player-name').value.trim() || 'Người chơi';
    
    // Hiện thông báo đang dùng AI sinh câu hỏi (AI mất vài giây suy nghĩ)
    const btn = document.getElementById('start-btn');
    const oldHtml = btn.innerHTML;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> ĐANG TẠO BỘ TỪ ĐIỂN MỚI...';
    btn.disabled = true;
    btn.style.opacity = '0.7';

    try {
        // Gọi API tới Python backend
        const res = await fetch(API_URL + '/api/game/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ player_name: playerName })
        });
        const data = await res.json();

        if (data.success) {
            // Lưu thông tin phiên
            sessionId = data.session_id;
            currentQuestion = 0;
            isAnswered = false;

            // Cập nhật giao diện
            document.getElementById('display-name').textContent = playerName;
            document.querySelectorAll('.lifeline-btn').forEach(b => b.classList.remove('used'));

            // Chuyển sang màn hình chơi
            switchScreen('game-screen');
            buildMoneyLadder();
            displayQuestion(data.question, data.question_number);
            addBotMessage(`Chào mừng ${playerName} đến với Ai Là Triệu Phú! 🎉 Chúc may mắn!`);
        } else {
            if (data.error && data.error.includes('hết lượt chơi')) {
                showModal('HẾT LƯỢT CHƠI 🎮', `
                    <div style="text-align:center; padding:10px 0;">
                        <p style="margin-bottom:20px; font-size:1.05rem; line-height:1.6; color:rgba(255,255,255,0.85);">
                            Bạn đã sử dụng hết lượt chơi miễn phí của mình. Hãy ghé qua cửa hàng để nhận thêm lượt hoặc nạp thêm nhé!
                        </p>
                        <button class="btn-start" onclick="closeModal(); openShop();" style="background: linear-gradient(135deg, var(--purple), var(--accent)); width:100%; border:none; padding:12px; font-family:'Outfit',sans-serif; font-weight:900; border-radius:9999px; color:#fff; cursor:pointer;">
                            🛒 GHÉ CỬA HÀNG MUA LƯỢT
                        </button>
                    </div>
                `);
            } else {
                alert('⚠️ Lỗi: ' + (data.error || 'Server không thể khởi tạo game.'));
            }
        }
    } catch (err) {
        // Lỗi kết nối server hoặc lỗi mạng
        alert('❌ Không thể khởi tạo phiên bản! (' + err + ')');
        console.error('Lỗi:', err);
    } finally {
        // Trả lại trạng thái cho nút
        btn.innerHTML = oldHtml;
        btn.disabled = false;
        btn.style.opacity = '1';
    }
}

// === HIỂN THỊ CÂU HỎI ===
function displayQuestion(q, num) {
    isAnswered = false;
    document.getElementById('question-number').textContent = `Câu hỏi ${num}/15`;
    document.getElementById('question-text').textContent = q.question;
    document.getElementById('current-prize').textContent = currentQuestion > 0 ? PRIZE_LEVELS[currentQuestion - 1] : '0 đ';

    // Hiển thị 4 đáp án
    for (let i = 0; i < 4; i++) {
        const btn = document.getElementById('answer-' + i);
        document.getElementById('text-' + i).textContent = q.answers[i];
        btn.className = 'answer-btn'; // Reset trạng thái
        btn.style.display = 'flex';
    }

    updateMoneyLadder();
    startTimer();
}

// === CẬP NHẬT BẢNG TIỀN ===
function updateMoneyLadder() {
    PRIZE_LEVELS.forEach((_, i) => {
        const li = document.getElementById('level-' + i);
        li.classList.remove('current', 'passed');
        if (MILESTONES.includes(i)) li.classList.add('milestone');
        if (i < currentQuestion) li.classList.add('passed');
        if (i === currentQuestion) li.classList.add('current');
    });
}

// === ĐỒNG HỒ ĐẾM NGƯỢC ===
function startTimer() {
    timeLeft = 30;
    clearInterval(timer);
    updateTimerDisplay();
    timer = setInterval(() => {
        timeLeft--;
        updateTimerDisplay();
        if (timeLeft <= 0) { clearInterval(timer); timeUp(); }
    }, 1000);
}

function updateTimerDisplay() {
    document.getElementById('timer-text').textContent = timeLeft;
    const circle = document.getElementById('timer-circle');
    circle.style.strokeDashoffset = 283 - (283 * timeLeft) / 30;
    circle.classList.remove('warning', 'danger');
    if (timeLeft <= 5) circle.classList.add('danger');
    else if (timeLeft <= 10) circle.classList.add('warning');
}

// === HẾT GIỜ - GỌI API /api/game/timeout ===
async function timeUp() {
    isAnswered = true;
    playSound('wrong');
    try {
        const res = await fetch(API_URL + '/api/game/timeout', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: sessionId })
        });
        const data = await res.json();
        if (data.success) {
            document.getElementById('answer-' + data.correct_answer).classList.add('correct');
            addBotMessage('⏰ Hết giờ! Đáp án đúng là ' + ['A', 'B', 'C', 'D'][data.correct_answer]);
            setTimeout(() => showResult(false, false, data), 2500);
        }
    } catch (err) { console.error(err); }
}

// === CHỌN ĐÁP ÁN - GỌI API /api/game/answer ===
async function selectAnswer(index) {
    if (isAnswered) return;
    isAnswered = true;
    clearInterval(timer);

    const btn = document.getElementById('answer-' + index);
    btn.classList.add('selected');
    playSound('select');

    // Đợi 2 giây (tạo kịch tính) rồi gửi lên server
    setTimeout(async () => {
        try {
            const res = await fetch(API_URL + '/api/game/answer', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ session_id: sessionId, answer: index })
            });
            const data = await res.json();

            btn.classList.remove('selected');

            if (data.is_correct) {
                // ĐÚNG!
                btn.classList.add('correct');
                playSound('correct');
                addBotMessage(getCorrectMsg());

                if (data.game_over && data.won) {
                    // THẮNG GAME!
                    setTimeout(() => {
                        showResult(true, true, data);
                        createConfetti();
                    }, 2000);
                } else {
                    // Câu tiếp theo
                    currentQuestion++;
                    setTimeout(() => displayQuestion(data.next_question, data.question_number), 2000);
                }
            } else {
                // SAI!
                btn.classList.add('wrong');
                document.getElementById('answer-' + data.correct_answer).classList.add('correct');
                playSound('wrong');
                addBotMessage(`❌ Sai rồi! Đáp án đúng là ${['A', 'B', 'C', 'D'][data.correct_answer]}`);
                setTimeout(() => showResult(false, false, data), 2500);
            }
        } catch (err) {
            console.error(err);
            alert('Lỗi kết nối server!');
        }
    }, 2000);
}

async function useLifeline(type) {
    if (isAnswered) return;
    const btn = document.getElementById('lifeline-' + type);
    
    if (btn.classList.contains('used')) {
        try {
            const wRes = await fetch(API_URL + '/api/shop/wallet');
            const wData = await wRes.json();
            if (wData.success) {
                const bonusCount = wData.bonus_lifelines;
                if (bonusCount <= 0) {
                    addBotMessage('⚠️ Bạn đã dùng quyền trợ giúp này và không còn lượt trợ giúp dự phòng. Hãy mua thêm tại cửa hàng!');
                    alert('⚠️ Bạn đã dùng quyền trợ giúp này và không còn lượt trợ giúp dự phòng nào trong ví.');
                    return;
                }
                const conf = confirm(`Bạn đã dùng quyền trợ giúp này. Bạn có muốn sử dụng 1 lượt trợ giúp dự phòng từ ví không? (Còn lại: ${bonusCount} lượt)`);
                if (!conf) return;
            } else {
                alert('Không thể tải ví của bạn!');
                return;
            }
        } catch(e) {
            alert('Lỗi kết nối ví!');
            return;
        }
    }

    try {
        const res = await fetch(API_URL + '/api/game/lifeline', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: sessionId, type: type })
        });
        const data = await res.json();

        if (!data.success) {
            addBotMessage('⚠️ ' + (data.error || 'Quyền trợ giúp đã dùng!'));
            return;
        }

        btn.classList.add('used');
        playSound('lifeline');

        if (data.type === '5050') {
            // Ẩn 2 đáp án sai
            data.removed.forEach(i => {
                document.getElementById('answer-' + i).classList.add('disabled');
            });
            const removedLetters = data.removed.map(i => ['A', 'B', 'C', 'D'][i]);
            showModal('50:50', `<div class="fifty-result"><div class="fifty-icon">✂️</div><p class="fifty-text">Đã loại 2 đáp án sai!</p><div class="fifty-removed">${removedLetters.map(l => `<span class="removed-answer">${l}</span>`).join('')}</div></div>`);
            addBotMessage('✂️ 50:50 đã loại 2 đáp án sai. Hãy cân nhắc kỹ!');
        }

        if (data.type === 'phone') {
            const letter = ['A', 'B', 'C', 'D'][data.suggestion];
            showModal('📞 Gọi điện cho người thân', `<div class="phone-result"><div class="phone-icon">📞</div><p class="phone-text">"Theo mình nghĩ đáp án là..."</p><p class="phone-answer">Đáp án ${letter} (${data.confidence}% chắc chắn)</p></div>`);
            addBotMessage(`📞 Người thân gợi ý đáp án ${letter} với ${data.confidence}% tự tin!`);
        }

        if (data.type === 'audience') {
            const letters = ['A', 'B', 'C', 'D'];
            showModal('👥 Hỏi ý kiến khán giả', `<div class="audience-chart">${letters.map((l, i) => `<div class="audience-bar"><div class="bar" style="height:${data.percents[i] * 1.5}px"><span class="bar-percent">${data.percents[i]}%</span></div><span class="bar-label">${l}</span></div>`).join('')}</div>`);
            addBotMessage('👥 Khán giả đã bình chọn! Xem biểu đồ để tham khảo.');
        }
    } catch (err) {
        console.error(err);
    }
}

// === DỪNG CUỘC CHƠI - GỌI API /api/game/stop ===
async function stopGame() {
    if (isAnswered) return;
    clearInterval(timer);
    isAnswered = true;

    try {
        const res = await fetch(API_URL + '/api/game/stop', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: sessionId })
        });
        const data = await res.json();
        if (data.success) {
            addBotMessage(`${playerName} dừng cuộc chơi và mang về ${data.prize}. Quyết định khôn ngoan! 🧠`);
            showResult(true, false, data);
        }
    } catch (err) { console.error(err); }
}

// === HIỂN THỊ KẾT QUẢ ===
function showResult(stopped, won, data) {
    let icon, title, message;

    if (won) {
        icon = '🏆'; title = 'CHÚC MỪNG TRIỆU PHÚ!';
        message = `${playerName} đã chinh phục tất cả 15 câu hỏi!`;
    } else if (stopped) {
        icon = '🎯'; title = 'Dừng cuộc chơi';
        message = `${playerName} đã dừng lại an toàn.`;
    } else {
        icon = '😢'; title = 'Tiếc quá!';
        message = `${playerName} đã trả lời sai ở câu ${data.correct_count + 1}.`;
    }

    document.getElementById('result-icon').textContent = icon;
    document.getElementById('result-title').textContent = title;
    document.getElementById('result-message').textContent = message;
    document.getElementById('prize-amount').textContent = data.prize;
    document.getElementById('correct-count').textContent = data.correct_count;
    document.getElementById('total-time').textContent = data.total_time + 's';

    // Gửi kết quả lên bảng xếp hạng
    saveToLeaderboard(data);
    switchScreen('result-screen');
}

// === LƯU BẢNG XẾP HẠNG ===
async function saveToLeaderboard(data) {
    try {
        await fetch(API_URL + '/api/leaderboard', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                player_name: playerName,
                correct_count: data.correct_count,
                prize: data.prize,
                total_time: data.total_time
            })
        });
    } catch (err) { console.error(err); }
}

// === MODAL ===
function showModal(title, body) {
    document.getElementById('modal-title').textContent = title;
    document.getElementById('modal-body').innerHTML = body;
    document.getElementById('modal-overlay').classList.add('active');
}
function closeModal() { document.getElementById('modal-overlay').classList.remove('active'); }

// === RESET GAME ===
function resetGame() {
    switchScreen('welcome-screen');
    addBotMessage('Chào mừng quay lại! 🎮 Sẵn sàng ván mới chưa?');
}

// === CHUYỂN MÀN HÌNH ===
function switchScreen(id) {
    document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
    document.getElementById(id).classList.add('active');
    if ((id === 'welcome-screen' || id === 'shop-screen') && typeof loadWallet === 'function') {
        loadWallet();
    }
}

// === HIỆU ỨNG PHÁO GIẤY ===
function createConfetti() {
    const colors = ['#ffd700', '#ff6b6b', '#4ecdc4', '#45b7d1', '#f9ca24', '#e056fd'];
    for (let i = 0; i < 80; i++) {
        const el = document.createElement('div');
        el.className = 'confetti-piece';
        el.style.left = Math.random() * 100 + 'vw';
        el.style.background = colors[Math.floor(Math.random() * colors.length)];
        el.style.animationDelay = Math.random() * 2 + 's';
        el.style.animationDuration = (2 + Math.random() * 3) + 's';
        el.style.width = (5 + Math.random() * 10) + 'px';
        el.style.height = (5 + Math.random() * 10) + 'px';
        document.body.appendChild(el);
        setTimeout(() => el.remove(), 5000);
    }
}

// === TIN NHẮN CHÚC MỪNG NGẪU NHIÊN ===
function getCorrectMsg() {
    const m = ["✅ Chính xác! 🎉", "✅ Đúng rồi! 💪", "✅ Xuất sắc! 🌟", "✅ Hoàn toàn chính xác! 👏", "✅ Bravo! 🏅"];
    return m[Math.floor(Math.random() * m.length)];
}

// ==========================================
// CHATBOT - GỌI API /api/chatbot
// ==========================================

function addBotMessage(text) {
    const c = document.getElementById('chatbot-messages');
    const d = document.createElement('div');
    d.className = 'chat-message bot';
    d.textContent = text;
    c.appendChild(d);
    c.scrollTop = c.scrollHeight;
    if (!chatbotOpen) {
        const b = document.getElementById('chat-badge');
        b.style.display = 'flex';
        b.textContent = parseInt(b.textContent || '0') + 1;
    }
}

// Gửi tin nhắn lên server
async function sendChat() {
    const input = document.getElementById('chat-input');
    const text = input.value.trim();
    if (!text) return;

    // Hiện tin nhắn người dùng
    const c = document.getElementById('chatbot-messages');
    const userDiv = document.createElement('div');
    userDiv.className = 'chat-message user';
    userDiv.textContent = text;
    c.appendChild(userDiv);
    input.value = '';

    // Hiện đang gõ
    const typing = document.createElement('div');
    typing.className = 'typing-indicator';
    typing.innerHTML = '<span></span><span></span><span></span>';
    c.appendChild(typing);
    c.scrollTop = c.scrollHeight;

    try {
        // GỌI API CHATBOT TRÊN SERVER
        const res = await fetch(API_URL + '/api/chatbot', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: text, session_id: sessionId })
        });
        const data = await res.json();
        typing.remove();
        addBotMessage(data.reply);
    } catch (err) {
        typing.remove();
        addBotMessage('⚠️ Lỗi kết nối server! Hãy kiểm tra server Python.');
    }
}

// Mở/đóng chatbot
function toggleChatbot() {
    chatbotOpen = !chatbotOpen;
    document.getElementById('chatbot-window').classList.toggle('active');
    if (chatbotOpen) {
        document.getElementById('chat-badge').style.display = 'none';
        document.getElementById('chat-badge').textContent = '0';
    }
}

// === DỊCH CÂU HỎI BẰNG API ===
let isTranslating = false;
async function translateQuestion(targetLang) {
    if (isTranslating || isAnswered || !sessionId) return;

    const btn = document.getElementById('translate-btn');
    const originalHTML = btn.innerHTML;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Đang dịch...';
    btn.disabled = true;
    btn.style.opacity = '0.7';
    isTranslating = true;

    try {
        const res = await fetch(API_URL + '/api/translate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: sessionId, target_lang: targetLang })
        });
        const data = await res.json();

        if (data.success && data.translated) {
            document.getElementById('question-text').textContent = data.translated.question;
            for (let i = 0; i < 4; i++) {
                if (data.translated.answers[i]) {
                    document.getElementById('text-' + i).textContent = data.translated.answers[i];
                }
            }

            // Xóa nội dung dịch sau vài giây hiển thị checkmark
            btn.innerHTML = '<i class="fas fa-check"></i> Đã dịch';
            setTimeout(() => {
                btn.innerHTML = originalHTML;
                btn.disabled = false;
                btn.style.opacity = '1';
                isTranslating = false;
            }, 3000);
        } else {
            alert('⚠️ ' + (data.error || 'Dịch thuật thất bại do lỗi cấu hình AI'));
            btn.innerHTML = originalHTML;
            btn.disabled = false;
            btn.style.opacity = '1';
            isTranslating = false;
        }
    } catch (err) {
        console.error(err);
        alert('Lỗi kết nối khi gọi AI!');
        btn.innerHTML = originalHTML;
        btn.disabled = false;
        btn.style.opacity = '1';
        isTranslating = false;
    }
}

// === ÂM THANH (Web Audio API) ===
const audioCtx = new (window.AudioContext || window.webkitAudioContext)();

function playSound(type) {
    if (!soundEnabled) return;
    const osc = audioCtx.createOscillator();
    const gain = audioCtx.createGain();
    osc.connect(gain); gain.connect(audioCtx.destination);
    gain.gain.value = 0.15;

    if (type === 'correct') {
        osc.frequency.value = 523; osc.type = 'sine';
        gain.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.5);
        osc.start(); osc.stop(audioCtx.currentTime + 0.5);
    } else if (type === 'wrong') {
        osc.frequency.value = 200; osc.type = 'sawtooth';
        gain.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.8);
        osc.start(); osc.stop(audioCtx.currentTime + 0.8);
    } else if (type === 'select') {
        osc.frequency.value = 440; osc.type = 'sine';
        gain.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.2);
        osc.start(); osc.stop(audioCtx.currentTime + 0.2);
    } else if (type === 'lifeline') {
        osc.frequency.value = 600; osc.type = 'triangle';
        gain.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.3);
        osc.start(); osc.stop(audioCtx.currentTime + 0.3);
    }
}

function toggleSound() {
    soundEnabled = !soundEnabled;
    document.getElementById('sound-icon').className = soundEnabled ? 'fas fa-volume-up' : 'fas fa-volume-mute';
}
