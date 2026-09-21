/* 저장소가 막힌 환경(쿠키 차단·일부 시크릿 모드)에서도 앱이 멈추지 않도록 메모리 저장으로 대체 */
function safeStorage(name) {
  try { const s = window[name]; s.setItem('__t', '1'); s.removeItem('__t'); return; } catch (e) { }
  const m = {};
  const mem = { getItem: k => (k in m ? m[k] : null), setItem: (k, v) => { m[k] = String(v); },
    removeItem: k => { delete m[k]; }, clear: () => Object.keys(m).forEach(k => delete m[k]) };
  try { Object.defineProperty(window, name, { configurable: true, value: mem }); } catch (e) { }
}
safeStorage('localStorage'); safeStorage('sessionStorage');

/* ===== 아래 탭 메뉴: 홈 · 지도 · 저장 · 최근 · 더보기 =====
   저장·최근은 기기(localStorage)에만 보관한다. 로그인·서버 저장 없음.
*/
const CONTACT_EMAIL = 'kosafmax1@naver.com';   // 문의·오류 제보 (사이트에 공개됨)

const STORE = {
  get(k) { try { return JSON.parse(localStorage.getItem(k) || '[]'); } catch (e) { return []; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { } },
};
const snap = it => ({ i: it.i, s: S.sido, n: it.n, p: it.p, m: it.m[0] ? it.m[0][0] : '', img: it.img,
  u: it.u, sb: it.s, g: it.g, t: Date.now() });

/* 저장(즐겨찾기) */
const isSaved = id => STORE.get('saved').some(x => x.i === id);
function toggleSave(it) {
  let list = STORE.get('saved');
  if (list.some(x => x.i === it.i)) list = list.filter(x => x.i !== it.i);
  else list.unshift(snap(it));
  STORE.set('saved', list.slice(0, 200));
  return isSaved(it.i);
}
/* 최근 본 업소(상세를 열 때 자동 기록, 최대 50) */
function addRecent(it) {
  const list = STORE.get('recent').filter(x => x.i !== it.i);
  list.unshift(snap(it));
  STORE.set('recent', list.slice(0, 50));
}

/* 저장·최근 목록 카드 → 누르면 해당 지역을 불러와 상세 열기 */
async function openSnap(x) {
  if (x.s !== S.sido) { S.center = null; S.my = null; await loadSido(x.s); renderArea(); }
  const it = S.items.find(i => i.i === x.i);
  showView('map');
  if (it) { apply(); openDetail(it); }
  else alert('이 업소는 최신 데이터에서 찾을 수 없습니다. 지정이 해제되었을 수 있습니다.');
}
function listView(title, key, emptyMsg) {
  const list = STORE.get(key);
  const when = t => { const d = (Date.now() - t) / 864e5; return d < 1 ? '오늘' : d < 2 ? '어제' : `${Math.floor(d)}일 전`; };
  return `<div class="pv-head"><h2>${title}</h2>${list.length ? `<button class="linkbtn" data-clear="${key}">전체 삭제</button>` : ''}</div>
    ${list.length ? `<ul class="pv-list">${list.map(x => `
      <li class="pv-item" data-id="${x.i}">
        <div class="thumb ph">${upIcon(x.u)}${x.img ? `<img decoding="async" data-src="${thumb(x)}" alt="" onload="this.classList.add('ok')" onerror="this.remove()">` : ''}</div>
        <div class="cbody"><div class="cprice">${x.p != null ? won(x.p) + '<span class="won">원</span>' : ''}<span class="cmenu">${x.m || ''}</span></div>
          <div class="cname">${x.n}</div>
          <div class="cmeta"><span>${x.g || ''}</span><span class="pill cat">${catLabel({ u: x.u, s: x.sb })}</span>
            ${key === 'recent' ? `<span>${when(x.t)}</span>` : ''}</div></div>
        ${key === 'saved' ? `<button class="pv-del" data-del="${x.i}" aria-label="저장 해제">♥</button>` : ''}
      </li>`).join('')}</ul>`
      : `<div class="pv-empty"><div>${key === 'saved' ? '♡' : '🕘'}</div>${emptyMsg}</div>`}`;
}
function renderList2(view) {
  const el = $('#pageView');
  el.innerHTML = view === 'saved'
    ? listView('저장한 업소', 'saved', '업소 상세에서 ♡를 누르면 여기에 모입니다.')
    : listView('최근 본 업소', 'recent', '업소 상세를 열면 자동으로 기록됩니다.');
  const key = view === 'saved' ? 'saved' : 'recent';
  el.querySelectorAll('.pv-item').forEach(li => li.onclick = e => {
    if (e.target.closest('.pv-del')) return;
    const x = STORE.get(key).find(v => v.i === li.dataset.id); if (x) openSnap(x);
  });
  el.querySelectorAll('[data-del]').forEach(b => b.onclick = () => {
    STORE.set('saved', STORE.get('saved').filter(v => v.i !== b.dataset.del)); renderList2(view);
  });
  el.querySelector('[data-clear]')?.addEventListener('click', () => {
    if (confirm(view === 'saved' ? '저장한 업소를 모두 지울까요?' : '최근 본 기록을 모두 지울까요?')) { STORE.set(key, []); renderList2(view); }
  });
}

/* 더보기 */
function renderMore() {
  const theme = localStorage.getItem('themeMode') || 'auto';
  const n = (typeof LIVE_NOTICES !== 'undefined' && LIVE_NOTICES) || [];
  $('#pageView').innerHTML = `
    <div class="pv-head"><h2>더보기</h2></div>

    ${typeof isInstalled === 'function' && isInstalled() ? '' : `<div class="mv-group"><h4>앱처럼 쓰기</h4>
      <button class="mv-row" id="mvInstall"><span>📲</span>홈 화면에 앱 아이콘 추가<i>›</i></button>
    </div>`}

    <div class="mv-group"><h4>착한가격업소 공식</h4>
      <a class="mv-row" href="https://www.goodprice.go.kr/" target="_blank" rel="noopener"><span>🏛</span>공식 누리집 바로가기<i>↗</i></a>
      <a class="mv-row" href="https://www.goodprice.go.kr/recent/insertBsshInfo.do" target="_blank" rel="noopener"><span>✏️</span>업소정보 오류 신고<i>↗</i></a>
      <a class="mv-row" href="https://www.goodprice.go.kr/recomm/recommend.do" target="_blank" rel="noopener"><span>👍</span>착한가격업소 추천하기<i>↗</i></a>
      <button class="mv-row" id="mvAbout"><span>ℹ️</span>착한가격업소란?<i>›</i></button>
    </div>

    ${n.length ? `<div class="mv-group"><h4>공식 소식 <small>하루 1회 갱신</small></h4>
      ${n.slice(0, 5).map(x => `<a class="mv-row" href="${NOTICE_URL}" target="_blank" rel="noopener">
        <span>${noticeIcon(x.title)}</span><b>${x.title}<small>${x.date}</small></b><i>↗</i></a>`).join('')}</div>` : ''}

    <div class="mv-group"><h4>설정</h4>
      <div class="mv-row static"><span>🌓</span>화면 모드
        <div class="seg">${[['auto', '자동'], ['light', '밝게'], ['dark', '어둡게']].map(([v, t]) =>
          `<button data-mode="${v}" aria-pressed="${theme === v}">${t}</button>`).join('')}</div></div>
      <div class="mv-row static"><span>📍</span>기준 위치
        <b class="mv-val">${S.refLabel || '지도 중심'}</b></div>
      <div class="mv-sub">
        <button class="chip" id="mvGps">내 위치(GPS)</button>
        <button class="chip" id="mvPin">지도에서 지정</button>
        <button class="chip" id="mvReset" ${S.refLabel ? '' : 'disabled'}>초기화</button>
      </div>
      <p class="mv-note">위치 권한은 휴대폰·브라우저 설정에서 관리됩니다. 한 번 거부했다면
        주소창 왼쪽 자물쇠(ⓘ) → 위치 → 허용으로 바꿔 주세요. 위치 정보는 기기 안에서만 쓰이고 저장·전송되지 않습니다.</p>
    </div>

    <div class="mv-group"><h4>정보</h4>
      <div class="mv-row static"><span>🗂</span>데이터 기준<b class="mv-val">${S.meta?.updated || ''}</b></div>
      <div class="mv-row static"><span>🏪</span>전체 업소<b class="mv-val">${(S.meta?.total || 0).toLocaleString()}곳</b></div>
      <p class="mv-note">자료: 행정안전부 착한가격업소(goodprice.go.kr), 공공데이터포털(data.go.kr)<br>
        좌표·장소 확인: 카카오·네이버·도로명주소·소상공인시장진흥공단 상가정보</p>
      <button class="mv-row" id="mvPrivacy"><span>🔒</span>개인정보 처리 안내<i>›</i></button>
      ${CONTACT_EMAIL ? `<a class="mv-row" href="mailto:${CONTACT_EMAIL}?subject=${encodeURIComponent('[착한가격 지도] 문의')}"><span>✉️</span>문의·오류 제보<b class="mv-val">${CONTACT_EMAIL}</b></a>` : ''}
      <p class="mv-note"><b>이 앱에 대하여</b><br>행정안전부 착한가격업소 공공데이터를 기반으로 개인이 만든 비공식 서비스입니다.
        정보가 실제와 다를 수 있으니 방문 전 업소에 확인해 주세요. 지정·취소 등 공식 문의는 해당 시군구 담당부서로 해 주세요.</p>
    </div>`;

  document.querySelectorAll('[data-mode]').forEach(b => b.onclick = () => { setThemeMode(b.dataset.mode); renderMore(); });
  $('#mvGps').onclick = () => { showView('map'); $('#gpsBtn').click(); };
  $('#mvPin').onclick = () => { showView('map'); if (!S.pinMode) $('#pinBtn').click(); };
  $('#mvReset').onclick = () => { $('#refClear').click(); renderMore(); };
  $('#mvAbout').onclick = renderAbout;
  $('#mvPrivacy').onclick = renderPrivacy;
  if ($('#mvInstall')) $('#mvInstall').onclick = installApp;
}

/* 착한가격업소란? — 공식 표찰·스티커 사진(출처 표기) */
function renderAbout() {
  $('#pageView').innerHTML = `
    <div class="pv-head"><button class="linkbtn" id="aboutBack">‹ 더보기</button><h2>착한가격업소란?</h2></div>
    <div class="about">
      <img class="about-logo only-light" src="assets/logo-circle.png" alt="착한가격"><img class="about-logo only-dark" src="assets/logo-circle-dark.png" alt="착한가격">
      <p>정부와 지방자치단체가 <b>저렴한 가격</b>, <b>청결한 가게</b>, <b>친절한 서비스</b>를 기준으로 지정한 물가안정 모범업소입니다.
        2011년부터 운영되고 있으며, 업소에는 아래와 같은 표찰이나 스티커가 붙어 있습니다.</p>
      <img class="about-sign" src="assets/sign-official.png" alt="착한가격업소 표찰과 스티커">
      <p class="mv-note">이미지 출처: 행정안전부 착한가격업소 누리집(goodprice.go.kr). 표찰의 지자체명은 지정 기관에 따라 다릅니다.</p>
      <h4>지정 기준</h4>
      <ul><li>가격: 지역 인근 상권 평균가격 미만</li><li>위생·청결: 주방·매장·화장실 관리 수준</li>
        <li>공공성: 지역화폐 가맹, 지역사회 공헌 등</li></ul>
      <a class="btn primary" href="https://www.goodprice.go.kr/intro/custInfo.do" target="_blank" rel="noopener">공식 누리집에서 자세히 보기 ↗</a>
    </div>`;
  $('#aboutBack').onclick = renderMore;
}

/* 화면 모드: 자동(기기 설정) / 밝게 / 어둡게 */
function setThemeMode(mode) {
  try { localStorage.setItem('themeMode', mode); } catch (e) { }
  const t = mode === 'auto' ? (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light') : mode;
  setTheme(t);
}

/* 탭 바 */
function renderTabbar() {
  const tabs = [
    ['home', '홈', '<path d="M3 11l9-7 9 7v9a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z"/>'],
    ['map', '지도', '<path d="M9 4L3 6v14l6-2 6 2 6-2V4l-6 2z"/><path d="M9 4v14M15 6v14"/>'],
    ['saved', '저장', '<path d="M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10z"/>'],
    ['recent', '최근', '<circle cx="12" cy="12" r="8"/><path d="M12 8v4l3 2"/>'],
    ['more', '더보기', '<circle cx="5" cy="12" r="1.3"/><circle cx="12" cy="12" r="1.3"/><circle cx="19" cy="12" r="1.3"/>'],
  ];
  const v = document.body.dataset.view;
  $('#tabbar').innerHTML = `<img class="rail-logo only-light" src="assets/logo-circle.png" alt="홈" data-tab="home">
    <img class="rail-logo only-dark" src="assets/logo-circle-dark.png" alt="홈" data-tab="home">` + tabs.map(([k, t, svg]) =>
    `<button class="tb ${v === k ? 'on' : ''}" data-tab="${k}" aria-label="${t}"><svg viewBox="0 0 24 24">${svg}</svg><span>${t}</span></button>`).join('');
  $('#tabbar').querySelectorAll('[data-tab]').forEach(b => b.onclick = () => showView(b.dataset.tab));
}

/* 홈 화면에 추가: 안드로이드·PC 크롬은 설치 창, 아이폰은 안내 문구 */
let installEvt = null;
addEventListener('beforeinstallprompt', e => { e.preventDefault(); installEvt = e; });
addEventListener('appinstalled', () => { installEvt = null; });
async function installApp() {
  const standalone = matchMedia('(display-mode: standalone)').matches || navigator.standalone;
  if (standalone) return guideBox('이미 홈 화면 앱으로 실행 중입니다.');
  if (installEvt && !IN_APP) {                       // 안드로이드 크롬 등: 설치 창 바로 띄우기
    installEvt.prompt();
    const r = await installEvt.userChoice; installEvt = null;
    if (r.outcome === 'accepted') return guideBox('홈 화면에 추가했습니다. 바탕화면의 <b>착한가격지도</b> 아이콘으로 실행하세요.');
  }
  guideBox('<h3>홈 화면에 앱 아이콘 추가</h3>' + installGuideHTML());
}
function guideBox(html) {                            // 간단한 안내 창
  document.querySelector('.guidebox')?.remove();
  document.body.insertAdjacentHTML('beforeend', `<div class="guidebox" role="dialog"><div class="gb-in">${html}
    <button class="btn primary" id="gbOk">확인</button></div></div>`);
  $('#gbOk').onclick = () => document.querySelector('.guidebox').remove();
  if ($('#gbExt')) $('#gbExt').onclick = openExternal;
}

/* 개인정보 처리 안내 */
function renderPrivacy() {
  $('#pageView').innerHTML = `
    <div class="pv-head"><button class="linkbtn" id="pvBack">‹ 더보기</button><h2>개인정보 처리 안내</h2></div>
    <div class="about">
      <h4>수집하지 않습니다</h4>
      <p>이 앱은 회원가입이 없고, 이름·연락처 등 개인정보를 수집하거나 서버에 저장하지 않습니다.</p>
      <h4>기기 안에만 저장되는 것</h4>
      <ul><li>저장한 업소, 최근 본 업소, 화면 모드 설정</li>
        <li>브라우저 저장공간에만 보관되며 서버로 전송되지 않습니다. 브라우저 기록을 지우면 함께 삭제됩니다.</li></ul>
      <h4>위치 정보</h4>
      <p>'내 위치'를 누르면 기기에서 받은 위치로 업소까지의 거리만 계산합니다. 위치는 서버로 전송·저장되지 않고 제3자에게 제공되지 않습니다.</p>
      <h4>문장 검색 (AI 해석)</h4>
      <p>앱이 스스로 이해하지 못한 검색 문장에 한해, 해석을 위해 <b>검색 문장만</b> Google Gemini API로 전송합니다.
        무료 이용 조건상 Google의 서비스 개선에 활용될 수 있으므로 <b>검색창에 개인정보를 입력하지 마세요.</b></p>
      <h4>접속 기록·방문 통계</h4>
      <p>사이트 운영 서비스(Cloudflare)가 보안·장애 대응을 위해 접속 기록(IP 등)을 일시적으로 남길 수 있습니다.
        방문 통계는 쿠키 없이 집계되며 개인을 식별하지 않습니다.</p>
      <h4>외부 서비스로 이동</h4>
      <p>길찾기·후기 보기 등은 카카오·네이버·구글·티맵으로 연결되며, 이동 후에는 해당 서비스의 정책이 적용됩니다.</p>
      ${CONTACT_EMAIL ? `<p class="mv-note">문의: ${CONTACT_EMAIL}</p>` : ''}
    </div>`;
  $('#pvBack').onclick = renderMore;
}
