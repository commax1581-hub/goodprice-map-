/* ===== PC·태블릿 전용 동작 =====
   - 시작 화면: PC(1100px 이상)는 지도, 그 외는 홈
   - 목록 위 추천 1줄(접이식)
   - 목록 마우스 올림 → 지도 마커 강조 / 키보드 ↑↓ 이동, Enter 열기
   - 홈 가로 묶음: ‹ › 버튼, 마우스 휠 좌우 이동
*/
/* 목록·홈·저장 카드용 사진: 미리 줄여 둔 사본 (gen_thumbs.py → thumbs/<관리번호>.webp) */
const thumb = o => `thumbs/${o.i}.webp`;
const isPC = () => matchMedia('(min-width:1100px)').matches;

/* ── 추천 1줄 ── */
function renderReco() {
  const box = $('#reco'); if (!box || typeof sectionDefs !== 'function') return;
  const closed = localStorage.getItem('recoClosed') === '1';
  let base = S.items.filter(i => !S.sgg || i.g === S.sgg);
  if (S.upjong) base = base.filter(i => matchCat(i, S.upjong, ''));
  const ref = S.my || S.center;
  base.forEach(i => { i._hd = ref ? dist(ref.y, ref.x, i.y, i.x) : null; });
  const prev = { upjong: HOME.upjong, sub: HOME.sub };
  HOME.upjong = S.upjong; HOME.sub = S.sub;                // 현재 지도 조건 기준으로 묶음 계산
  const defs = sectionDefs(base, ref ? { ...ref, label: '' } : null, '').filter(d => d.list.length);
  HOME.upjong = prev.upjong; HOME.sub = prev.sub;
  box.className = 'reco' + (closed ? ' closed' : '');
  box.innerHTML = `
    <button class="reco-h" id="recoToggle">✨ 추천 ${closed ? '▸' : '▾'}<span class="rc">${closed ? '펼치기' : '접기'}</span></button>
    <div class="reco-row">${defs.map(d => `<button class="rchip" data-reco="${d.key}">${d.title}<b>${d.list.length}</b>›</button>`).join('')}</div>`;
  $('#recoToggle').onclick = () => { localStorage.setItem('recoClosed', closed ? '0' : '1'); renderReco(); };
  box.querySelectorAll('[data-reco]').forEach(b => b.onclick = () => {
    const d = defs.find(x => x.key === b.dataset.reco); if (!d) return;
    const ap = { upjong: S.upjong, ...d.apply };
    if (ap.upjong === S.upjong) ap.sub = S.sub;                // 같은 업종이면 세부업종 유지
    goMapWith(ap);
  });
}

/* ── 마우스 올림 → 마커 강조(주황) ── */
const HOVER_IMG = {};
function hoverImage() {
  if (HOVER_IMG.v) return HOVER_IMG.v;
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="36" height="43" viewBox="0 0 30 36">
    <path d="M15 35C15 35 27 22.5 27 14A12 12 0 1 0 3 14c0 8.5 12 21 12 21z" fill="#F59F0A" stroke="#fff" stroke-width="2.5"/>
    <circle cx="15" cy="14" r="4.5" fill="#fff"/></svg>`;
  HOVER_IMG.v = new kakao.maps.MarkerImage('data:image/svg+xml;base64,' + btoa(svg),
    new kakao.maps.Size(36, 43), { offset: new kakao.maps.Point(18, 43) });
  return HOVER_IMG.v;
}
let hoverId = null;
function hoverMarker(id, on) {
  if (!S.markerById || typeof kakao === 'undefined') return;
  if (hoverId && hoverId !== S.selMarkerId && S.markerById[hoverId]) {
    S.markerById[hoverId].setImage(markerImage(false)); S.markerById[hoverId].setZIndex(1);
  }
  hoverId = on ? id : null;
  const mk = S.markerById[id];
  if (on && mk && id !== S.selMarkerId) { mk.setImage(hoverImage()); mk.setZIndex(15); }
  hoverLabel(on ? id : null);
}
/* PC 전용 말풍선: 묶음(숫자) 안에 있어도 위치에 이름·가격 표시 */
let hoverOv = null;
function hoverLabel(id) {
  if (!S.map || !isPC()) return;
  const it = id && S.items.find(i => i.i === id);
  if (!it) { if (hoverOv) hoverOv.setMap(null); return; }
  const el = document.createElement('div'); el.className = 'hvlabel';
  const rm = it._sm || repMenu(it);
  el.innerHTML = `<b>${it.n}</b>${rm ? `<span>${rm[0]} ${won(rm[1])}원</span>` : ''}`;
  if (hoverOv) hoverOv.setMap(null);
  hoverOv = new kakao.maps.CustomOverlay({ position: new kakao.maps.LatLng(it.y, it.x), content: el,
    yAnchor: 1, xAnchor: 0.5, zIndex: 30, clickable: false });
  hoverOv.setMap(S.map);
}

/* ── 키보드 이동 ── */
let kbIndex = -1;
function kbMove(step) {
  const cards = [...document.querySelectorAll('#list .card')]; if (!cards.length) return;
  cards.forEach(c => c.classList.remove('kb'));
  kbIndex = Math.max(0, Math.min(cards.length - 1, kbIndex + step));
  const c = cards[kbIndex]; c.classList.add('kb'); c.scrollIntoView({ block: 'nearest' });
  hoverMarker(c.dataset.id, true);
}

function initPC() {
  // 목록 위 추천 줄 자리
  if (!$('#reco')) {
    const r = document.createElement('div'); r.id = 'reco';
    $('#listpane').insertBefore(r, $('#list'));
  }
  renderReco();
  // 키보드 안내
  if (!document.querySelector('.kbhint')) $('.listhead').insertAdjacentHTML('beforeend',
    '<span class="kbhint"><kbd>↑</kbd><kbd>↓</kbd> 이동 <kbd>Enter</kbd> 열기</span>');

  // 목록 마우스 올림 (이벤트 위임)
  $('#list').addEventListener('mouseover', e => {
    const c = e.target.closest('.card'); if (!c) return;
    document.querySelectorAll('#list .card.hv').forEach(x => x !== c && x.classList.remove('hv'));
    c.classList.add('hv'); hoverMarker(c.dataset.id, true);
  });
  $('#list').addEventListener('mouseleave', () => {
    document.querySelectorAll('#list .card.hv').forEach(x => x.classList.remove('hv'));
    if (hoverId) hoverMarker(hoverId, false);
  });

  // 키보드: 입력창에 있을 때는 동작하지 않음
  document.addEventListener('keydown', e => {
    if (document.body.dataset.view !== 'map' || /INPUT|SELECT|TEXTAREA/.test(document.activeElement.tagName)) return;
    if (e.key === 'ArrowDown') { e.preventDefault(); kbMove(1); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); kbMove(-1); }
    else if (e.key === 'Enter' && kbIndex >= 0 && document.activeElement === document.body) {
      const c = document.querySelectorAll('#list .card')[kbIndex]; if (c) c.click();
    } else if (e.key === 'Escape' && !$('#detail').hidden) { $('#dclose').click(); }
  });

  // 홈 가로 묶음: 마우스 휠 → 좌우 이동, ‹ › 버튼
  document.addEventListener('wheel', e => {
    const rail = e.target.closest('.hrail'); if (!rail || Math.abs(e.deltaX) > Math.abs(e.deltaY)) return;
    const max = rail.scrollWidth - rail.clientWidth; if (max <= 0) return;
    const next = rail.scrollLeft + e.deltaY;
    if (next <= 0 && e.deltaY < 0 || next >= max && e.deltaY > 0) return;   // 끝에 닿으면 페이지 스크롤 허용
    e.preventDefault(); rail.scrollLeft = next;
  }, { passive: false });
  document.addEventListener('click', e => {
    const b = e.target.closest('[data-harr]'); if (!b) return;
    const rail = b.closest('.hsec').querySelector('.hrail');
    rail.scrollBy({ left: (b.dataset.harr === 'next' ? 1 : -1) * rail.clientWidth * 0.9, behavior: 'smooth' });
  });
}

/* ── 사진 지연 로딩: 화면에 들어온 이미지만 요청, 동시 요청 수 제한 ── */
const IMG_Q = { active: 0, max: 6, queue: [] };
function pumpImg() {
  while (IMG_Q.active < IMG_Q.max && IMG_Q.queue.length) {
    const img = IMG_Q.queue.shift(); if (!img.isConnected || !img.dataset.src) continue;
    IMG_Q.active++;
    const done = () => { IMG_Q.active--; pumpImg(); };
    img.addEventListener('load', done, { once: true });
    img.addEventListener('error', done, { once: true });
    img.src = img.dataset.src; delete img.dataset.src;
  }
}
const imgObserver = 'IntersectionObserver' in window ? new IntersectionObserver(entries => {
  entries.forEach(e => { if (e.isIntersecting) { imgObserver.unobserve(e.target); IMG_Q.queue.push(e.target); } });
  pumpImg();
}, { rootMargin: '200px' }) : null;
function watchImages(root) {
  (root || document).querySelectorAll('img[data-src]').forEach(img => {
    if (imgObserver) imgObserver.observe(img); else { img.src = img.dataset.src; }
  });
}
new MutationObserver(muts => muts.forEach(m => m.addedNodes.forEach(n => {
  if (n.nodeType === 1) { if (n.matches && n.matches('img[data-src]')) watchImages(n.parentNode); else watchImages(n); }
}))).observe(document.body, { childList: true, subtree: true });
