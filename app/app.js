/* ===== 착한가격 지도 — 프로토타입 ===== */
const S = {
  meta: null, items: [], filtered: [], sido: '11', sgg: '', upjong: '', sub: '',
  pinMode: false, refLabel: '', pinMarker: null,
  quick: new Set(), fac: new Set(), maxPrice: null, sort: 'dist',
  center: null, my: null, page: 0, PAGE: 40, sel: null, map: null, markers: [], cluster: null, markerById: {}, selMarkerId: null,
};
const $ = s => document.querySelector(s);
const WD = ['월', '화', '수', '목', '금', '토', '일'];
const UPJONG = [
  ['', '전체'], ['한식', '한식'], ['중식', '중식'], ['일식', '일식'], ['양식', '양식'],
  ['카페·빵', '카페·빵'], ['미용·이발', '미용·이발'], ['생활', '생활'],
];
const SUBS = { 한식: ['일반', '육류', '면류', '분식', '찌개류', '한정식', '해산물', '기타'] };
/* 업종 묶음: 데이터의 업종 값은 그대로 두고 화면에서만 묶는다. 묶음의 세부 칩 = 원래 업종 [업종 값, 칩 이름] */
const GROUPS = {
  '카페·빵': [['기타요식업', '카페·기타'], ['베이커리', '베이커리']],
  '미용·이발': [['미용업', '미용'], ['이용업', '이용']],
  '생활': [['세탁업', '세탁'], ['목욕업', '목욕'], ['숙박업', '숙박'], ['기타비요식업', '기타']],
};
const UJ_GROUP = {};
Object.entries(GROUPS).forEach(([g, list]) => list.forEach(([u]) => { UJ_GROUP[u] = g; }));
// 업소 업종 → 칩 값 (한식·중식·일식·양식은 그대로, 묶음에 없는 새 업종은 생활로 보내 사라지지 않게)
const groupOf = u => ['한식', '중식', '일식', '양식'].includes(u) ? u : UJ_GROUP[u] || '생활';
// 세부 칩 목록 [값, 이름]: 한식은 세부분류, 묶음은 원래 업종
const subList = uj => GROUPS[uj] || (SUBS[uj] ? SUBS[uj].map(s => [s, s]) : null);
// 업종 칩·세부 칩 조건에 맞는지 (한식 세부 칩은 세부분류로, 묶음 세부 칩은 업종으로 거른다)
function matchCat(it, uj, sub) {
  if (uj && groupOf(it.u) !== uj) return false;
  if (sub) return GROUPS[uj] ? it.u === sub : it.s === sub;
  return true;
}
// 조건 문구: 미용·이발·이용, 카페·기타, 생활·기타, 한식·면류
function ujText(uj, sub) {
  if (!sub) return uj;
  if (!GROUPS[uj]) return `${uj}·${sub}`;
  if (sub === '기타요식업') return '카페·기타';
  const s = (GROUPS[uj].find(x => x[0] === sub) || [])[1] || sub;
  return `${uj}·${s}`;
}
// 업소 카드의 업종 표시
const catLabel = it => GROUPS[groupOf(it.u)] ? ujText(groupOf(it.u), it.u) : it.s ? `${it.u}·${it.s}` : it.u;

/* ---------- 유틸 ---------- */
const upIcon = u => ({ 한식: '🍚', 중식: '🥟', 일식: '🍣', 양식: '🍝', 베이커리: '🥐', 기타요식업: '☕',
  미용업: '✂️', 이용업: '💈', 세탁업: '👕', 목욕업: '♨️', 숙박업: '🏨' }[u] || '🏪');
const won = n => n == null ? '' : n.toLocaleString('ko-KR');
const dist = (a, b, c, d) => {
  const R = 6371000, p1 = a * Math.PI / 180, p2 = c * Math.PI / 180;
  const dp = p2 - p1, dl = (d - b) * Math.PI / 180;
  const x = Math.sin(dp / 2) ** 2 + Math.cos(p1) * Math.cos(p2) * Math.sin(dl / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(x));
};
const fmtDist = m => m == null ? '' : m < 1000 ? `${Math.round(m / 10) * 10}m` : `${(m / 1000).toFixed(1)}km`;
const isOpenNow = it => {
  if (!it.o || !it.c) return null;
  const now = new Date(), day = (now.getDay() + 6) % 7;
  if (it.w && it.w.split(',').includes(String(day))) return false;
  const cur = now.getHours() * 60 + now.getMinutes();
  const [oh, om] = it.o.split(':').map(Number), [ch, cm] = it.c.split(':').map(Number);
  let s = oh * 60 + om, e = ch * 60 + cm;
  if (e <= s) e += 1440;
  return (cur >= s && cur <= e) || (cur + 1440 >= s && cur + 1440 <= e);
};
const q = s => encodeURIComponent(s);
const links = it => ({
  official: it.sn ? `https://www.goodprice.go.kr/bssh/bsshInfo.do?bsshSn=${it.sn}` : '',
  kakao: it.k ? `https://place.map.kakao.com/${it.k}` : `https://map.kakao.com/link/map/${q(it.n)},${it.y},${it.x}`,
  roadview: `https://map.kakao.com/link/roadview/${it.y},${it.x}`,
  naver: `https://map.naver.com/p/search/${q(it.n + ' ' + it.g)}`,
  google: `https://www.google.com/maps/search/?api=1&query=${q(it.n + ' ' + it.a)}`,
  navi_kakao: `https://map.kakao.com/link/to/${q(it.n)},${it.y},${it.x}`,
  navi_naver: `https://map.naver.com/p/directions/-/${it.x},${it.y},${q(it.n)}/-/transit`,
  navi_google: `https://www.google.com/maps/dir/?api=1&destination=${q(it.n + ' ' + it.a)}`,   // 좌표 대신 이름+주소
  navi_tmap: `tmap://route?goalname=${q(it.n)}&goalx=${it.x}&goaly=${it.y}`,
  streetview: `https://www.google.com/maps/@?api=1&map_action=pano&viewpoint=${it.y},${it.x}`,
});

/* ---------- 스마트 검색 안내 ---------- */
function hintPill(msg) {
  let el = document.querySelector('.hintpill');
  if (!msg) { el?.remove(); return; }
  if (!el) { el = document.createElement('div'); el.className = 'hintpill'; $('.searchbar').appendChild(el); }
  el.textContent = msg;
}
let smartTimer;
function setSmartNote(msg, ms) {
  const el = $('#smartNote'); if (!el) return;
  el.textContent = msg; el.hidden = false;
  clearTimeout(smartTimer);
  if (ms) smartTimer = setTimeout(() => el.hidden = true, ms);
}
function describeShort(p) {
  const b = [];
  if (p.region) b.push(p.region.name);
  else if (p.keptArea) b.push(`${p.keptArea}(보던 지역)`);
  if (p.upjong) b.push(ujText(p.upjong, p.sub));
  if (p.keyword) b.push(`'${p.keyword}'`);
  if (p.maxPrice) b.push(won(p.maxPrice) + '원 이하');
  p.conds.forEach(c => b.push(c === 'open' ? '영업중' : c === 'photo' ? '사진' : c.slice(4)));
  return b.join(' · ') || '전체';
}

/* ---------- 공유 / URL 상태 ---------- */
function shareUrl(it) {
  const u = new URL(location.href);
  u.search = ''; u.hash = '';
  u.searchParams.set('s', S.sido);
  u.searchParams.set('id', it.i);
  return u.toString();
}
function shareText(it) {
  const m = it.m[0];
  return [`${it.n} (착한가격업소)`,
          m ? `${m[0]} ${won(m[1])}원` : '',
          it.a, it.t || ''].filter(Boolean).join(String.fromCharCode(10));
}
async function shareItem(it, btn) {
  const url = shareUrl(it), text = shareText(it);
  if (navigator.share) {
    try { await navigator.share({ title: it.n, text, url }); return; }
    catch (e) { if (e.name === 'AbortError') return; }
  }
  try {
    await navigator.clipboard.writeText(text + String.fromCharCode(10) + url);
    if (btn) { const o = btn.textContent; btn.textContent = '복사됨 ✓'; setTimeout(() => btn.textContent = o, 1500); }
  } catch (e) {
    prompt('아래 주소를 복사하세요', url);
  }
}
function syncUrl(it) {
  const u = new URL(location.href);
  u.searchParams.set('s', S.sido);
  if (it) u.searchParams.set('id', it.i); else u.searchParams.delete('id');
  history.replaceState(history.state, '', u);
}

/* ---------- 테마 ---------- */
function initTheme() {
  let mode = null;
  try { mode = localStorage.getItem('themeMode'); localStorage.removeItem('theme'); } catch (e) { }
  const mq = matchMedia('(prefers-color-scheme: dark)');
  setTheme(!mode || mode === 'auto' ? (mq.matches ? 'dark' : 'light') : mode);
  // 자동 모드일 때 기기 설정이 바뀌면 바로 따라감
  mq.addEventListener?.('change', () => {
    let m = null; try { m = localStorage.getItem('themeMode'); } catch (e) { }
    if (!m || m === 'auto') { setTheme(mq.matches ? 'dark' : 'light'); if (document.body.dataset.view === 'home') renderHome(); }
  });
  $('#theme').onclick = () => setThemeMode(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark');
}
function setTheme(t) {
  document.documentElement.dataset.theme = t;
  $('#themeIcon').textContent = t === 'dark' ? '☀️' : '🌙';
}

/* ---------- 데이터 ---------- */
async function getJSON(url, opt) {
  try {
    const r = await fetch(url, opt);
    if (!r.ok) throw new Error('HTTP ' + r.status);
    return await r.json();
  } catch (e) { loadFail(); throw e; }
}
function loadFail() {                   // 통신이 끊겼거나 서버 오류일 때
  if (document.querySelector('.loadfail')) return;
  document.body.insertAdjacentHTML('beforeend', `<div class="loadfail" role="alert">
    <b>데이터를 불러오지 못했습니다</b><span>인터넷 연결을 확인한 뒤 다시 시도해 주세요.</span>
    <button onclick="location.reload()">다시 시도</button></div>`);
}
async function loadMeta() {
  S.meta = await getJSON('data/index.json', { cache: 'no-cache' });
}
async function loadSido(code) {
  if (code !== S.sido) S.sgg = '';
  S.sido = code;
  S.items = await getJSON(`data/${code}.json?v=${encodeURIComponent(S.meta.updated || '')}`);
  const s = S.meta.sido.find(x => x.code === code);
  $('#areaLabel').textContent = s ? s.name : '';
  renderSgg();
  apply();
  fitMap();
}

/* ---------- 지역 선택 ---------- */
function renderArea() {
  const a = $('#selSido');
  a.innerHTML = S.meta.sido.map(x =>
    `<option value="${x.code}" ${x.code === S.sido ? 'selected' : ''}>${x.name} (${x.count.toLocaleString()})</option>`).join('');
  renderSgg();
}
function renderSgg() {
  const cnt = {};
  S.items.forEach(it => cnt[it.g] = (cnt[it.g] || 0) + 1);
  const list = Object.keys(cnt).sort();
  $('#selSgg').innerHTML = `<option value="">시군구 전체 (${S.items.length.toLocaleString()})</option>` +
    list.map(g => `<option value="${g}" ${g === S.sgg ? 'selected' : ''}>${g} (${cnt[g].toLocaleString()})</option>`).join('');
}
function setRef(pt, label) {
  S.my = pt; S.center = pt; S.refLabel = label;
  $('#refNote').textContent = label ? `기준: ${label}` : '';
  $('#refNote').hidden = !label; $('#refClear').hidden = !label;
  if (S.map && pt) {
    if (S.pinMarker) S.pinMarker.setMap(null);
    S.pinMarker = new kakao.maps.Marker({
      position: new kakao.maps.LatLng(pt.y, pt.x), map: S.map, zIndex: 10,
      image: new kakao.maps.MarkerImage(
        'data:image/svg+xml;base64,' + btoa('<svg xmlns="http://www.w3.org/2000/svg" width="26" height="26"><circle cx="13" cy="13" r="8" fill="#F59F0A" stroke="white" stroke-width="3"/></svg>'),
        new kakao.maps.Size(26, 26)),
    });
  }
  apply();
}

/* ---------- 필터 ---------- */
// 한 글자 검색어는 엉뚱한 곳에 걸린다('회' → PT 10회권, 마을회관). 메뉴 이름에서 규칙으로 판별
const KW_RULES = {
  // 메뉴의 '회'(생선회·멸치회·회국수·회덮밥·회비빔밥)는 인정, 숫자 뒤(10회)·육회·다회용기·회관·상회·회사·회원·회차·회당·회비는 제외. 업소명은 횟집·회센터만
  '회': it => /횟집|회센터|활어/.test(it.n) || it.m.some(m => /(?<![0-9육다])회(?![관사원차권의당]|비(?!빔))/.test(m[0] || '') && !/(상회|교회|협회|회관)/.test(m[0] || '')),
};

function apply() {
  const kw = $('#q').value.trim().toLowerCase();
  const ref = S.my || S.center;
  let r = S.items.filter(it => {
    if (S.sgg && it.g !== S.sgg) return false;
    if (!matchCat(it, S.upjong, S.sub)) return false;
    if (kw) {
      const hay = (it.n + ' ' + it.m.map(m => m[0]).join(' ')).toLowerCase();
      if (KW_RULES[kw] ? !KW_RULES[kw](it) : !hay.includes(kw)) return false;
    }
    if (S.maxPrice && !(it.p != null && it.p <= S.maxPrice)) return false;
    if (S.quick.has('photo') && !it.img) return false;
    if (S.quick.has('open') && isOpenNow(it) !== true) return false;
    for (const f of S.fac) if (!it.f.includes(f)) return false;
    return true;
  });
  r.forEach(it => { it._d = ref ? dist(ref.y, ref.x, it.y, it.x) : null; });
  r.sort(S.sort === 'price'
    ? (a, b) => (a.p ?? 9e9) - (b.p ?? 9e9)
    : (a, b) => (a._d ?? 9e9) - (b._d ?? 9e9));
  S.filtered = r; S.page = 0;
  $('#count').textContent = r.length.toLocaleString('ko-KR');
  let on = $('#openNote');                                  // 영업중 필터: 영업시간 등록 업소만 대상
  if (!on) { on = document.createElement('span'); on.id = 'openNote'; on.className = 'opennote'; $('#count').parentNode.insertBefore(on, $('#count').nextSibling.nextSibling); }
  on.textContent = S.quick.has('open') ? '(영업시간 등록 업소 중)' : '';
  // 정렬 표시: 기준 위치가 없으면 거리를 계산할 수 없으므로 '기본순'
  $('#sortBtn').textContent = (S.sort === 'price' ? '가격순' : ref ? '거리순' : '기본순') + ' ▾';
  renderList(); renderMarkers();
  if (typeof kbIndex !== 'undefined') kbIndex = -1;
  if (typeof renderReco === 'function') renderReco();
}

/* ---------- 목록 ---------- */
function card(it) {
  const op = isOpenNow(it);
  const menu = it.m[0];
  const price = it.p ?? (menu ? menu[1] : null);
  const li = document.createElement('li');
  li.className = 'card'; li.dataset.id = it.i;
  li.innerHTML = `
    <div class="thumb ph">${upIcon(it.u)}${it.img ? `<img decoding="async" data-src="${thumb(it)}" alt="" onload="this.classList.add('ok')" onerror="this.remove()">` : ''}</div>
    <div class="cbody">
      <div class="cprice">${price != null ? won(price) + '<span class="won">원</span>' : '<span class="won">가격 정보 없음</span>'}
        ${menu ? `<span class="cmenu">${menu[0]}</span>` : ''}</div>
      <div class="cname">${it.n}</div>
      <div class="cmeta">
        ${it._d != null ? `<span>${fmtDist(it._d)}</span><i class="dot"></i>` : ''}
        <span class="pill cat">${catLabel(it)}</span>
        ${op === true ? '<span class="pill open">영업중</span>' : op === false ? '<span class="pill closed">영업종료</span>' : ''}
        ${it.f.includes('포장') ? '<span class="pill closed">포장</span>' : ''}
        ${it.f.includes('배달') ? '<span class="pill closed">배달</span>' : ''}
      </div>
    </div>`;
  li.onclick = () => openDetail(it);
  return li;
}
function renderList(append) {
  const ul = $('#list');
  if (!append) { ul.innerHTML = ''; ul.scrollTop = 0; }
  const start = S.page * S.PAGE;
  S.filtered.slice(start, start + S.PAGE).forEach(it => ul.appendChild(card(it)));
  $('#more').hidden = (start + S.PAGE) >= S.filtered.length;
  if (!S.filtered.length && !append)
    ul.innerHTML = '<li style="padding:40px 16px;text-align:center;color:var(--fg-mute)">조건에 맞는 업소가 없습니다.<br>필터를 줄여보세요.</li>';
}

/* ---------- 상세 ---------- */
function openDetail(it) {
  S.sel = it;
  const L = links(it), op = isOpenNow(it);
  const el = $('#detail'); el.hidden = false;
  el.innerHTML = `
    <div class="dbar"><button class="dback" id="dback" aria-label="닫기">‹ 목록</button>
      <span class="dbar-t">${it.n}</span></div>
    <div class="dhero">
      ${it.img ? `<img src="${it.img}" alt="${it.n}" style="background:center/cover url(${thumb(it)})"
        onerror="if(!this.dataset.f){this.dataset.f=1;this.src='${thumb(it)}'}else{this.outerHTML='<div class=noimg>${upIcon(it.u)}</div>'}">` : `<div class="noimg">${upIcon(it.u)}</div>`}
      <button class="dclose" id="dclose">✕</button>
    </div>
    <div class="dbody">
      <div class="dtitlerow">
        <div>
          <h2 class="dtitle">${it.n}
            <span class="gpbadge" title="착한가격업소 지정"><img class="only-light" src="assets/logo-pill.png" alt="착한가격업소"><img class="only-dark" src="assets/logo-pill-dark.png" alt="착한가격업소"></span>
            ${L.official ? `<a class="offbadge" href="${L.official}" target="_blank" rel="noopener" title="공식 정보">공식정보 ↗</a>` : ''}
          </h2>
          <div class="dsub">
            <span class="pill cat">${catLabel(it)}</span>
            ${op === true ? '<span class="pill open">영업중</span>' : op === false ? '<span class="pill closed">영업종료</span>' : ''}
            <span>${it.g} ${it.e || ''}</span>
            ${it._d != null ? `<i class="dot"></i><span>${fmtDist(it._d)}</span>` : ''}
          </div>
        </div>
        <button class="sharebtn savebtn ${isSaved(it.i) ? 'on' : ''}" id="saveBtn" title="저장" aria-label="저장">${isSaved(it.i) ? '♥' : '♡'}</button>
        <button class="sharebtn kakaobtn" id="kakaoBtn" title="카카오톡으로 공유" aria-label="카카오톡으로 공유">
          <svg viewBox="0 0 24 24" width="20" height="20"><path fill="currentColor" d="M12 3.5C6.8 3.5 2.6 6.8 2.6 10.9c0 2.6 1.7 4.9 4.3 6.2l-1 3.7c-.1.3.3.6.6.4l4.4-2.9c.4 0 .7.1 1.1.1 5.2 0 9.4-3.3 9.4-7.5S17.2 3.5 12 3.5z"/></svg>
        </button>
        <button class="sharebtn" id="shareBtn" title="공유하기" aria-label="공유하기">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2"
               stroke-linecap="round" stroke-linejoin="round">
            <circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/>
            <path d="M8.6 13.5l6.8 4M15.4 6.5l-6.8 4"/></svg>
        </button>
      </div>

      <div class="menubox">
        <h4>착한가격 메뉴 ${it.m.length > 1 ? `(${it.m.length})` : ''}</h4>
        ${it.m.map(m => `<div class="menurow"><span class="mn">${m[0]}${m[2] ? '<span class="star">지정</span>' : ''}</span>
          <span class="mp">${m[1] ? won(m[1]) + '원' : '-'}</span></div>`).join('') || '<div class="menurow muted">메뉴 정보 없음</div>'}
      </div>

      <dl class="infogrid">
        <dt>주소</dt><dd>${it.a}${it.bd ? ` (${it.bd})` : ''}</dd>
        ${it.t ? `<dt>전화</dt><dd class="telrow"><span>${it.t}</span><a class="minibtn" href="tel:${it.t}">전화걸기</a></dd>` : ''}
        <dt>영업시간</dt><dd>${it.h ? it.h.replace(/\s*\/\s*/g, '<br>') : '<span class="muted">미확인</span>'}</dd>
        ${it.w ? `<dt>휴무</dt><dd>${it.w.split(',').map(d => WD[+d]).join('·')}요일</dd>` : ''}
      </dl>

      ${it.f.length ? `<div class="facs">${it.f.map(f => `<span class="fac">${f}</span>`).join('')}</div>` : ''}

      <div class="sec-title">길찾기</div>
      <div class="btnrow btnrow4">
        <a class="btn" href="${L.navi_kakao}" target="_blank" rel="noopener">카카오맵</a>
        <a class="btn" href="${L.navi_naver}" target="_blank" rel="noopener">네이버맵</a>
        <a class="btn" href="${L.navi_google}" target="_blank" rel="noopener">구글맵</a>
        <a class="btn tmapbtn" href="${L.navi_tmap}">티맵</a>
      </div>

      <div class="sec-title">후기 보기</div>
      <div class="btnrow">
        <a class="btn" href="${L.naver}" target="_blank" rel="noopener">네이버</a>
        <a class="btn" href="${L.google}" target="_blank" rel="noopener">구글</a>
        <a class="btn" href="${L.kakao}" target="_blank" rel="noopener">카카오맵</a>
      </div>

      <div class="sec-title">현장 확인</div>
      <div class="btnrow">
        <a class="btn ghost" href="${L.roadview}" target="_blank" rel="noopener">카카오 로드뷰</a>
        <a class="btn ghost" href="${L.streetview}" target="_blank" rel="noopener">구글 거리뷰</a>
      </div>

      <p class="src">
        자료: 행정안전부 착한가격업소(goodprice.go.kr), 공공데이터포털<br>
        ${it.dept ? `문의: ${it.dept} ${it.dtel || ''}<br>` : ''}
        사진: 공식 누리집 원본(목록에는 작게 줄인 사본).  본 앱은 비공식 개인 프로젝트입니다.
      </p>
    </div>`;
  // 닫기·목록·휴대폰 뒤로가기 모두 같은 경로로: 기록이 있으면 back → popstate에서 닫음
  const requestClose = () => (history.state && history.state.detail) ? history.back() : hideDetail();
  $('#dback').onclick = requestClose;
  $('#dclose').onclick = requestClose;
  if (!(history.state && history.state.detail)) history.pushState({ detail: it.i }, '', location.href);
  el.scrollTop = 0; el.classList.remove('scrolled');
  el.onscroll = () => el.classList.toggle('scrolled', el.scrollTop > 180);
  $('#shareBtn').onclick = e => shareItem(it, e.currentTarget);
  $('#kakaoBtn').onclick = () => kakaoShare(it);
  $('#saveBtn').onclick = e => { const on = toggleSave(it); e.currentTarget.classList.toggle('on', on); e.currentTarget.textContent = on ? '♥' : '♡'; };
  addRecent(it);
  syncUrl(it);
  document.querySelectorAll('.card').forEach(c => c.classList.toggle('active', c.dataset.id === it.i));
  highlightMarker(it.i);
  if (S.map) S.map.panTo(new kakao.maps.LatLng(it.y, it.x));
}

/* ---------- 지도 ---------- */
function initMap() {
  if (window.__kakaoFail || typeof kakao === 'undefined' || !kakao.maps) { $('#mapfallback').hidden = false; $('#origin').textContent = location.origin; return; }
  kakao.maps.load(() => {
    S.map = new kakao.maps.Map($('#map'), { center: new kakao.maps.LatLng(37.5665, 126.978), level: 5 });
    S.map.addControl(new kakao.maps.ZoomControl(), kakao.maps.ControlPosition.RIGHT);
    S.cluster = new kakao.maps.MarkerClusterer({ map: S.map, averageCenter: true, minLevel: 7, disableClickZoom: false });
    kakao.maps.event.addListener(S.map, 'dragend', () => $('#research').hidden = false);
    kakao.maps.event.addListener(S.map, 'dragstart', () => { if (typeof onMapDragMobile === 'function') onMapDragMobile(); });
    kakao.maps.event.addListener(S.map, 'click', e => {
      if (!S.pinMode) return;
      const ll = e.latLng;
      setRef({ y: ll.getLat(), x: ll.getLng() }, '지도에서 지정한 위치');
      S.pinMode = false; $('#pinBtn').classList.remove('on');
      document.body.classList.remove('pinmode'); document.querySelector('.pinhint')?.remove();
    });
    $('#research').onclick = () => {
      const c = S.map.getCenter();
      S.center = { y: c.getLat(), x: c.getLng() }; S.my = null;
      $('#research').hidden = true; apply();
    };
    renderMarkers(); fitMap();
  });
}
const MK_IMG = {};
function markerImage(sel) {
  const k = sel ? 'sel' : 'def';
  if (MK_IMG[k]) return MK_IMG[k];
  const fill = sel ? '#E03131' : '#2453C7';
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${sel ? 40 : 30}" height="${sel ? 48 : 36}" viewBox="0 0 30 36">
    <path d="M15 35C15 35 27 22.5 27 14A12 12 0 1 0 3 14c0 8.5 12 21 12 21z" fill="${fill}" stroke="#fff" stroke-width="2.5"/>
    <circle cx="15" cy="14" r="4.5" fill="#fff"/></svg>`;
  MK_IMG[k] = new kakao.maps.MarkerImage(
    'data:image/svg+xml;base64,' + btoa(unescape(encodeURIComponent(svg))),
    new kakao.maps.Size(sel ? 40 : 30, sel ? 48 : 36),
    { offset: new kakao.maps.Point(sel ? 20 : 15, sel ? 48 : 36) });
  return MK_IMG[k];
}
function renderMarkers() {
  if (!S.map || !S.cluster) return;
  if (S.mkItems !== S.items) { S.mkCache = {}; S.mkItems = S.items; }   // 시도가 바뀌면 새로 만듦
  S.markerById = {};
  const ms = S.filtered.map(it => {             // 묶음(클러스터)이 처리하므로 전부 표시
    let mk = S.mkCache[it.i];
    if (!mk) {
      mk = new kakao.maps.Marker({ position: new kakao.maps.LatLng(it.y, it.x), title: it.n, image: markerImage(false) });
      kakao.maps.event.addListener(mk, 'click', () => openDetail(it));
      S.mkCache[it.i] = mk;
    }
    S.markerById[it.i] = mk;
    return mk;
  });
  if (S.sel) highlightMarker(S.sel.i);
  // 묶음 다시 그리기는 넓은 지역에서 무거우므로: 결과가 같으면 생략, 연달아 호출되면 마지막 한 번만
  const sig = S.sido + ':' + S.filtered.map(i => i.i).sort().join(',');   // 정렬 순서만 바뀐 경우도 같은 결과
  if (sig === S.mkSig) return;
  S.mkSig = sig;
  clearTimeout(S.mkTimer);
  S.mkTimer = setTimeout(() => { S.cluster.clear(); S.cluster.addMarkers(ms, true); S.cluster.redraw(); }, 30);
}
function highlightMarker(id) {
  if (!S.markerById) return;
  if (S.selMarkerId && S.markerById[S.selMarkerId]) {
    S.markerById[S.selMarkerId].setImage(markerImage(false));
    S.markerById[S.selMarkerId].setZIndex(1);
  }
  const mk = S.markerById[id];
  if (mk) { mk.setImage(markerImage(true)); mk.setZIndex(20); }
  S.selMarkerId = id;
}
function fitMap() {
  if (!S.map || !S.filtered.length) return;
  const b = new kakao.maps.LatLngBounds();
  S.filtered.slice(0, 300).forEach(it => b.extend(new kakao.maps.LatLng(it.y, it.x)));
  // 모바일: 아래 목록 시트가 가리는 만큼 여백을 줘서 보이는 영역에 맞춤
  const mobile = matchMedia('(max-width:760px)').matches;
  const sheetH = mobile ? ($('#listpane').getBoundingClientRect().height || 0) : 0;
  S.map.setBounds(b, 40, 40, sheetH + 30, 40);
  setTimeout(() => $('#research').hidden = true, 300);
}

/* ---------- 칩/필터 UI ---------- */
function renderChips() {
  const box = $('#chips'); box.innerHTML = '';
  UPJONG.forEach(([v, label]) => {
    const b = document.createElement('button');
    b.className = 'chip'; b.textContent = label;
    b.setAttribute('aria-pressed', String(S.upjong === v));
    b.onclick = () => { S.upjong = v; S.sub = ''; renderChips(); renderSub(); apply(); };
    box.appendChild(b);
  });
  renderSub();
}
function renderSub() {
  const box = $('#subchips'), list = subList(S.upjong);
  if (!list) { box.hidden = true; return; }
  box.hidden = false; box.innerHTML = '';
  [['', '전체'], ...list].forEach(([v, label]) => {
    const b = document.createElement('button');
    b.className = 'chip sub-chip'; b.textContent = label;
    b.setAttribute('aria-pressed', String(S.sub === v));
    b.onclick = () => { S.sub = v; renderSub(); apply(); };
    box.appendChild(b);
  });
}
function renderFilterModal() {
  const facs = ['주차', '포장', '배달', '예약', '단체가능', '와이파이', '반려동물', '유아시설', '장애인시설', '임산부우대', '지역화폐', '남녀화장실'];
  $('#filterBody').innerHTML = `
    <div class="fgroup"><h4>최대 가격 <span id="fPriceLabel" class="muted">${S.maxPrice ? won(S.maxPrice) + '원 이하' : '제한 없음'}</span></h4>
      <div class="range"><input type="range" id="fPrice" min="0" max="30000" step="1000" value="${S.maxPrice || 0}"></div></div>
    <div class="fgroup"><h4>편의시설</h4><div class="chips" id="fFacs">
      ${facs.map(f => `<button class="chip" data-fac="${f}" aria-pressed="${S.fac.has(f)}">${f}</button>`).join('')}
    </div></div>`;
  $('#fPrice').oninput = e => {
    const v = +e.target.value;
    $('#fPriceLabel').textContent = v ? won(v) + '원 이하' : '제한 없음';
  };
  $('#fFacs').onclick = e => {
    const b = e.target.closest('[data-fac]'); if (!b) return;
    const on = b.getAttribute('aria-pressed') === 'true';
    b.setAttribute('aria-pressed', String(!on));
  };
}
function filterCount() {
  const n = S.fac.size + (S.maxPrice ? 1 : 0);
  const b = $('#filterCount'); b.hidden = !n; b.textContent = n;
}

/* ---------- 이벤트 ---------- */
let searchSeq = 0;
function bind() {
  let t;
  $('#q').oninput = e => {
    const v = e.target.value;
    $('#qclear').hidden = !v;
    const isSentence = /\s/.test(v.trim());
    hintPill(isSentence ? 'Enter를 누르면 문장으로 검색합니다' : '');
    clearTimeout(t);
    if (isSentence) return;                 // 문장은 Enter 전까지 조회하지 않음
    t = setTimeout(apply, 180);
  };
  $('#q').onkeydown = async e => {                       // Enter = 문장 해석 검색
    if (e.key !== 'Enter') return;
    const text = e.target.value.trim(); if (!text) return;
    hintPill('');
    if (typeof parseQuery !== 'function') return;
    const dict = buildRegionDict(S.meta);
    setSmartNote('문장을 해석하는 중…');
    const my = ++searchSeq;                              // 가장 최근 검색의 답만 적용(늦게 온 이전 답 무시)
    let p = parseQuery(text, dict, S.items);
    let src = '', aiFailed = false;
    if (p.hits <= 1 && typeof aiParse === 'function') {
      try { const ai = await aiParse(text, dict); p = mergeRule(ai, p); src = 'AI'; }
      catch (err) { aiFailed = true; /* 규칙 결과로 진행(실패·8초 초과) */ }
    }
    if (my !== searchSeq) return;
    if (p.hits === 0) {
      setSmartNote(aiFailed ? 'AI 해석이 잠시 안 돼요. 잠시 뒤 다시 시도하거나 지역·메뉴 위주로 입력해 주세요'
        : '조건을 못 읽었어요. 단어 검색으로 표시합니다', aiFailed ? 5000 : 2500);
      apply(); return;
    }
    await applyParsed(p);
    const relaxed = p.relaxed && p.relaxed.length ? ` → ${p.relaxed.join(', ')} 조건은 결과가 없어 뺐어요` : '';
    setSmartNote(describeShort(p) + (src ? ` · ${src} 해석` : '') + relaxed, relaxed ? 6000 : 3500);
  };
  $('#qclear').onclick = () => { $('#q').value = ''; $('#qclear').hidden = true; hintPill(''); apply(); };
  document.querySelectorAll('[data-quick]').forEach(b => b.onclick = () => {
    const k = b.dataset.quick;
    S.quick.has(k) ? S.quick.delete(k) : S.quick.add(k);
    b.classList.toggle('on', S.quick.has(k)); apply();
  });
  $('#sortBtn').onclick = () => {
    S.sort = S.sort === 'dist' ? 'price' : 'dist';
    apply();
  };
  $('#more').onclick = () => { S.page++; renderList(true); };
  $('#selSido').onchange = async e => {
    S.sgg = ''; S.center = null; S.my = null; S.refLabel = '';
    $('#refNote').hidden = true; $('#refClear').hidden = true;            // 이전 지역의 기준 위치 표시 제거
    if (S.pinMarker) { S.pinMarker.setMap(null); S.pinMarker = null; }
    if (S.pinMode) $('#pinBtn').click();                                 // 위치 지정 모드 해제
    await loadSido(e.target.value); renderSgg(); if (document.body.dataset.view === 'home') renderHome(); };
  $('#selSgg').onchange = e => { S.sgg = e.target.value; apply(); fitMap(); if (document.body.dataset.view === 'home') renderHome(); };
  $('#pinBtn').onclick = () => {
    S.pinMode = !S.pinMode;
    $('#pinBtn').classList.toggle('on', S.pinMode);
    document.body.classList.toggle('pinmode', S.pinMode);
    let hint = document.querySelector('.pinhint');
    if (S.pinMode) {
      if (!hint) { hint = document.createElement('div'); hint.className = 'pinhint'; hint.textContent = '지도를 클릭해 기준 위치를 지정하세요'; $('.mappane').appendChild(hint); }
    } else if (hint) hint.remove();
  };
  $('#priceChip').onclick = e => {
    document.querySelector('.popover')?.remove();
    const pop = document.createElement('div'); pop.className = 'popover';
    const opts = [[null, '가격 제한 없음'], [3000, '3,000원 이하'], [5000, '5,000원 이하'], [7000, '7,000원 이하'], [10000, '10,000원 이하']];
    pop.innerHTML = opts.map(([v, t]) => `<button data-v="${v ?? ''}" aria-pressed="${S.maxPrice === v}">${t}</button>`).join('');
    const r = e.currentTarget.getBoundingClientRect();
    pop.style.left = r.left + 'px'; pop.style.top = (r.bottom + 6) + 'px';
    document.body.appendChild(pop);
    pop.onclick = ev => {
      const b = ev.target.closest('button'); if (!b) return;
      S.maxPrice = b.dataset.v ? +b.dataset.v : null;
      $('#priceChip').textContent = (S.maxPrice ? won(S.maxPrice) + '원 이하' : '가격') + ' ▾';
      $('#priceChip').classList.toggle('on', !!S.maxPrice);
      pop.remove(); apply();
    };
    setTimeout(() => document.addEventListener('click', function h(ev2) {
      if (!pop.contains(ev2.target)) { pop.remove(); document.removeEventListener('click', h); }
    }), 0);
  };
  $('#gpsBtn').onclick = () => {
    if (!navigator.geolocation) return alert('이 브라우저는 위치를 지원하지 않습니다.');
    navigator.geolocation.getCurrentPosition(
      async p => {
        const acc = Math.round(p.coords.accuracy || 0);
        if (acc > 3000 && !confirm(`현재 위치 정확도가 약 ${(acc/1000).toFixed(1)}km로 낮습니다.
PC는 GPS가 없어 부정확할 수 있습니다.
그래도 이 위치를 기준으로 할까요? (취소 후 '지도에서 위치 지정'을 권장합니다)`)) return;
        if (typeof moveToRegionOf === 'function') await moveToRegionOf(p.coords.latitude, p.coords.longitude);   // 내 위치의 시도로 전환
        S.sort = 'dist';
        setRef({ y: p.coords.latitude, x: p.coords.longitude }, `내 위치(오차 ±${acc < 1000 ? acc + 'm' : (acc/1000).toFixed(1) + 'km'})`);
        if (S.map) { S.map.setCenter(new kakao.maps.LatLng(p.coords.latitude, p.coords.longitude)); S.map.setLevel(4); }
      },
      () => alert('위치를 가져오지 못했습니다. PC에서는 지도를 움직여 "이 지역에서 다시 검색"을 눌러주세요.'),
      { enableHighAccuracy: true, timeout: 8000 });
  };
  $('#refClear').onclick = () => {
    S.my = null; S.refLabel = '';
    $('#refNote').hidden = true; $('#refClear').hidden = true;
    if (S.pinMarker) { S.pinMarker.setMap(null); S.pinMarker = null; }
    if (S.map) { const c = S.map.getCenter(); S.center = { y: c.getLat(), x: c.getLng() }; }
    apply();
  };
  $('#moreFilter').onclick = () => { renderFilterModal(); $('#filterModal').hidden = false; };
  $('#closeFilter').onclick = () => $('#filterModal').hidden = true;
  $('#resetFilter').onclick = () => {
    document.querySelectorAll('#fFacs [aria-pressed]').forEach(b => b.setAttribute('aria-pressed', 'false'));
    $('#fPrice').value = 0; $('#fPriceLabel').textContent = '제한 없음';
  };
  $('#applyFilter').onclick = () => {
    S.fac = new Set([...document.querySelectorAll('#fFacs [aria-pressed="true"]')].map(b => b.dataset.fac));
    S.maxPrice = +$('#fPrice').value || null;
    $('#priceChip').textContent = (S.maxPrice ? won(S.maxPrice) + '원 이하' : '가격') + ' ▾';
    $('#priceChip').classList.toggle('on', !!S.maxPrice);
    $('#filterModal').hidden = true; filterCount(); apply();
  };
  // 모바일 목록 시트·앱 안 브라우저 안내 (mobile.js)
  if (typeof initMobile === 'function') initMobile();
}

/* ---------- 인트로 연동 ---------- */
async function applyParsed(p) {
  // 지역
  if (p.region) {
    if (p.region.code !== S.sido) { S.center = null; S.my = null; await loadSido(p.region.code); renderArea(); }
    S.sgg = p.region.type === 'sgg' ? p.region.name : '';
    $('#selSido').value = S.sido; renderSgg();
  } else if (!p.near && !p.dong) {        // 문장에 지역이 없으면 보던 지역에서 찾는다 → 문구에 표시
    p.keptArea = S.sgg || (S.meta.sido.find(x => x.code === S.sido) || {}).name || '';
  }
  // 업종·검색어
  S.upjong = p.upjong || ''; S.sub = p.sub || '';
  $('#q').value = p.keyword || '';
  $('#qclear').hidden = !p.keyword;
  renderChips();
  // 가격
  S.maxPrice = p.maxPrice || null;
  $('#priceChip').textContent = (S.maxPrice ? won(S.maxPrice) + '원 이하' : '가격') + ' ▾';
  $('#priceChip').classList.toggle('on', !!S.maxPrice);
  // 조건
  S.quick.clear(); S.fac.clear();
  p.conds.forEach(c => c.startsWith('fac:') ? S.fac.add(c.slice(4)) : S.quick.add(c));
  document.querySelectorAll('[data-quick]').forEach(b => b.classList.toggle('on', S.quick.has(b.dataset.quick)));
  filterCount();
  // 행정동 → 해당 동 첫 업소를 기준점으로
  if (p.dong) {
    const hit = S.items.find(i => i.e === p.dong);
    if (hit) setRef({ y: hit.y, x: hit.x }, p.dong);
  }
  // 내 주변
  if (p.near && navigator.geolocation) {
    await new Promise(res => navigator.geolocation.getCurrentPosition(
      async pos => {
        if (typeof moveToRegionOf === 'function') await moveToRegionOf(pos.coords.latitude, pos.coords.longitude);
        setRef({ y: pos.coords.latitude, x: pos.coords.longitude }, '내 위치'); res();
      },
      () => res(), { timeout: 6000 }));
  }
  apply();
  // 결과가 0곳이면 조건을 하나씩 풀어서 다시 찾고, 뺀 조건을 알려준다
  p.relaxed = [];
  const steps = [
    [() => $('#q').value.trim(), () => { p.relaxed.push(`'${$('#q').value.trim()}'`); $('#q').value = ''; $('#qclear').hidden = true; }],
    [() => S.maxPrice, () => {
      p.relaxed.push(won(S.maxPrice) + '원 이하'); S.maxPrice = null;
      $('#priceChip').textContent = '가격 ▾'; $('#priceChip').classList.remove('on');
    }],
    [() => S.fac.size || S.quick.size, () => {
      p.relaxed.push([...S.fac, ...[...S.quick].map(q => q === 'open' ? '지금 영업중' : '사진 있음')].join('·'));
      S.fac.clear(); S.quick.clear();
      document.querySelectorAll('[data-quick]').forEach(b => b.classList.remove('on')); filterCount();
    }],
    [() => S.sub, () => { p.relaxed.push(ujText(S.upjong, S.sub)); S.sub = ''; renderSub(); }],
  ];
  for (const [has, drop] of steps) {
    if (S.filtered.length) break;
    if (!has()) continue;
    drop(); apply();
  }
  if (!p.dong && !p.near) fitMap();
  return S.filtered.length;
}

function hideDetail() {
  const el = $('#detail'); if (el.hidden) return;
  if (typeof installNudge === 'function') setTimeout(installNudge, 600);
  el.hidden = true; S.sel = null; syncUrl(null);
  if (S.selMarkerId && S.markerById[S.selMarkerId]) {
    S.markerById[S.selMarkerId].setImage(markerImage(false)); S.selMarkerId = null;
  }
}
window.addEventListener('popstate', hideDetail);

/* ---------- 시작 ---------- */
(async function main() {
  initTheme(); bind();
  await loadMeta();
  loadNotices().then(() => { if (document.body.dataset.view === 'home') renderHome(); });
  renderChips();
  const qs = new URLSearchParams(location.search);
  await loadSido(qs.get('s') && S.meta.sido.some(x => x.code === qs.get('s')) ? qs.get('s') : '11');
  renderArea();
  initMap();
  if (typeof initPC === 'function') initPC();
  $('#brandHome').onclick = () => showView('home');
  const sharedId = qs.get('id');
  const hit = sharedId && S.items.find(i => i.i === sharedId);
  if (hit) {                            // 공유 링크로 들어온 경우 해당 업소 바로 열기
    showView('map'); setRef({ y: hit.y, x: hit.x }, '공유된 업소 위치'); openDetail(hit); sessionStorage.setItem('introSeen', '1');
  } else {
    showView(typeof isPC === 'function' && isPC() ? 'map' : 'home');
    if (sharedId) {                     // 지정 해제 등으로 사라진 업소
      syncUrl(null);
      setTimeout(() => alert('공유된 업소를 찾을 수 없습니다. 착한가격업소 지정이 해제되었을 수 있습니다.'), 300);
    }
  }
  if (typeof runIntro === 'function' && !sessionStorage.getItem('introSeen')) {
    sessionStorage.setItem('introSeen', '1');
    runIntro({ meta: S.meta, items: () => S.items,
      applyParsed: async p => { const n = await applyParsed(p); showView('map'); return n; } });
  }
})();
