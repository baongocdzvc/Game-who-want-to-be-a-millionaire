/* ==========================================
   SERVICE WORKER - Đã cấu hình để XÓA CACHE hoàn toàn
   File: sw.js
   ========================================== */

self.addEventListener('install', event => {
    // Ép phiên bản mới này cài đặt ngay lập tức
    self.skipWaiting();
});

self.addEventListener('activate', event => {
    console.log('✅ Service Worker: Đang dọn dẹp cache cũ...');
    // Xóa SẠCH tất cả các bộ nhớ đệm (caches) từ các phiên bản trước
    event.waitUntil(
        caches.keys().then(names => {
            return Promise.all(
                names.map(name => caches.delete(name))
            );
        }).then(() => {
            // Tự động hủy Service worker
            return self.registration.unregister();
        })
    );
});

// Xử lý fetch: Luôn gọi thẳng từ internet, không dùng cache nữa
self.addEventListener('fetch', event => {
    event.respondWith(fetch(event.request).catch(err => {
        console.error("Lỗi mạng:", err);
        throw err;
    }));
});
