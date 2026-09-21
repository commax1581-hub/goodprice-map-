/* 착한가격 지도 — 홈 화면 추가용 서비스 워커
   네트워크 우선: 평소엔 항상 최신 파일, 연결이 끊겼을 때만 마지막 저장본을 보여준다. */
const CACHE = 'goodprice-v1';
self.addEventListener('install', e => self.skipWaiting());
self.addEventListener('activate', e => e.waitUntil(
  caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim())));
self.addEventListener('fetch', e => {
  const u = new URL(e.request.url);
  if (e.request.method !== 'GET' || u.origin !== location.origin || u.pathname.startsWith('/api/')) return;
  e.respondWith(fetch(e.request).then(r => {
    if (r.ok) { const c = r.clone(); caches.open(CACHE).then(cc => cc.put(e.request, c)); }
    return r;
  }).catch(() => caches.match(e.request, { ignoreSearch: true })));
});
