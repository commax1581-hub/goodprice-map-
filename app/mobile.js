/* ===== 휴대폰 사용성 =====
   - 카카오톡 등 앱 안 브라우저 안내(홈 화면 추가·위치가 제한됨 → 기본 브라우저로 열기)
   - 목록 시트 3단계(작게·중간·크게), 지도 끌면 목록 자동으로 작게
   - 내 위치(GPS) → 그 위치의 시도로 자동 전환
   - 카카오톡으로 공유(카카오 공식 공유 기능)
   - 홈 화면에 추가(설치) 안내 강화
*/
const UA = navigator.userAgent;
const IN_APP = /KAKAOTALK/i.test(UA) ? 'kakao'
  : /NAVER\(inapp|Instagram|FBAN|FBAV|Line\/|DaumApps|everytimeApp|BAND\//i.test(UA) ? 'other' : '';
const IS_IOS = /iPhone|iPad|iPod/.test(UA);
const isMobile = () => matchMedia('(max-width:760px)').matches;

/* ── 앱 안 브라우저 안내 ── */
function openExternal() {
  const url = location.href;
  if (IN_APP === 'kakao') location.href = 'kakaotalk://web/openExternal?url=' + encodeURIComponent(url);
  else if (/Android/.test(UA)) location.href = 'intent://' + url.replace(/^https?:\/\//, '') + '#Intent;scheme=https;package=com.android.chrome;end';
  else alert('오른쪽 위(또는 아래) 메뉴에서 "다른 브라우저로 열기"(Safari로 열기)를 눌러 주세요.');
}
function inAppBanner() {
  if (!IN_APP) return;
  try { if (sessionStorage.getItem('inappClosed')) return; } catch (e) { }
  document.body.insertAdjacentHTML('afterbegin', `<div class="inapp" id="inapp">
    <span>${IN_APP === 'kakao' ? '카카오톡' : '앱'} 안에서는 <b>홈 화면 추가·내 위치</b>가 제한돼요.</span>
    <button id="inappOpen">브라우저로 열기</button><button class="x" id="inappX" aria-label="닫기">✕</button></div>`);
  $('#inappOpen').onclick = openExternal;
  $('#inappX').onclick = () => { $('#inapp').remove(); try { sessionStorage.setItem('inappClosed', '1'); } catch (e) { } };
}

/* ── 목록 시트: mini(지도 크게) · half · full ── */
function setSheet(s) {
  const pane = $('#listpane');
  pane.classList.toggle('expanded', s === 'full');
  pane.classList.toggle('collapsed', s === 'mini');
  S.sheet = s;
  const b = $('#sheetBtn');
  if (b) b.textContent = s === 'mini' ? '☰ 목록 보기' : '🗺 지도 보기';
}
function initSheet() {
  const pane = $('#listpane'), handle = $('#sheetHandle');
  if (!pane || !handle) return;
  pane.insertBefore(handle, pane.firstChild);                        // 손잡이를 시트 맨 위로
  if (!$('#sheetBtn')) $('.listhead').insertAdjacentHTML('beforeend', '<button class="sheetbtn" id="sheetBtn">🗺 지도 보기</button>');
  $('#sheetBtn').onclick = () => setSheet(S.sheet === 'mini' ? 'half' : 'mini');
  handle.onclick = () => setSheet(S.sheet === 'mini' ? 'half' : S.sheet === 'half' ? 'full' : 'half');
  // 위아래로 밀기
  let y0 = null;
  const start = e => { y0 = e.touches[0].clientY; };
  const end = e => {
    if (y0 == null) return;
    const dy = e.changedTouches[0].clientY - y0; y0 = null;
    if (Math.abs(dy) < 40) return;
    const order = ['mini', 'half', 'full'], i = order.indexOf(S.sheet || 'half');
    setSheet(order[Math.max(0, Math.min(2, i + (dy < 0 ? 1 : -1)))]);
  };
  [handle, $('.listhead')].forEach(el => { el.addEventListener('touchstart', start, { passive: true }); el.addEventListener('touchend', end); });
  setSheet('half');
}
function onMapDragMobile() { if (isMobile() && S.sheet === 'half') setSheet('mini'); }   // 지도를 움직이면 목록을 작게

/* ── 내 위치 → 그 위치의 시도로 전환 ── */
function sidoCodeOf(name) {
  const hit = S.meta.sido.find(s => s.name === name);
  if (hit) return hit.code;
  const short = name.replace(/(특별시|광역시|특별자치시|특별자치도|도)$/, '');
  const e = Object.entries(typeof SIDO_ALIAS !== 'undefined' ? SIDO_ALIAS : {}).find(([, ks]) => ks.includes(name) || ks.includes(short));
  return e ? e[0] : null;
}
function regionOfPoint(y, x) {
  return new Promise(res => {
    if (typeof kakao === 'undefined' || !kakao.maps.services) return res(null);
    new kakao.maps.services.Geocoder().coord2RegionCode(x, y, (r, st) => {
      if (st !== kakao.maps.services.Status.OK || !r.length) return res(null);
      const h = r.find(v => v.region_type === 'H') || r[0];
      res({ sido: h.region_1depth_name, sgg: h.region_2depth_name });
    });
  });
}
async function moveToRegionOf(y, x) {
  const rg = await regionOfPoint(y, x); if (!rg) return false;
  const code = sidoCodeOf(rg.sido); if (!code) return false;
  if (code !== S.sido) {
    S.sgg = ''; S.center = null;
    await loadSido(code); renderArea(); $('#selSido').value = code;
  }
  return true;
}

/* ── 카카오톡으로 공유 ── */
const KAKAO_JS_KEY = '6516210bcdd3c0a50b562ea3dedda4a3';
function loadKakaoSdk() {
  if (window.Kakao && Kakao.isInitialized && Kakao.isInitialized()) return Promise.resolve();
  return new Promise((res, rej) => {
    const s = document.createElement('script');
    s.src = 'https://t1.kakaocdn.net/kakao_js_sdk/2.7.2/kakao.min.js';
    s.onload = () => { try { if (!Kakao.isInitialized()) Kakao.init(KAKAO_JS_KEY); res(); } catch (e) { rej(e); } };
    s.onerror = rej;
    document.head.appendChild(s);
  });
}
async function kakaoShare(it) {
  const url = shareUrl(it), m = it.m[0];
  try {
    await loadKakaoSdk();
    Kakao.Share.sendDefault({
      objectType: 'feed',
      content: {
        title: `${it.n} · 착한가격업소`,
        description: [m && m[1] ? `${m[0]} ${won(m[1])}원` : '', it.a].filter(Boolean).join(' · '),
        imageUrl: new URL(it.img ? thumb(it) : 'assets/og-default.png', location.href).href,
        link: { mobileWebUrl: url, webUrl: url },
      },
      buttons: [{ title: '지도에서 보기', link: { mobileWebUrl: url, webUrl: url } }],
    });
  } catch (e) {
    shareItem(it);                                   // 실패하면 기본 공유(주소 복사)로
  }
}

/* ── 홈 화면에 추가(설치) ── */
function installGuideHTML() {
  if (IN_APP) return `<b>지금은 ${IN_APP === 'kakao' ? '카카오톡' : '앱'} 안에서 열려 있어 추가할 수 없어요.</b><br>
    아래 버튼으로 기본 브라우저(크롬·사파리)에서 연 뒤 다시 눌러 주세요.<br><button class="chip" onclick="openExternal()">브라우저로 열기</button>`;
  if (IS_IOS) return `<b>아이폰(사파리)</b><br>① 화면 아래 <b>공유 버튼(□↑)</b> → ② <b>홈 화면에 추가</b> → ③ 오른쪽 위 <b>추가</b>`;
  if (/SamsungBrowser/.test(UA)) return `<b>삼성 인터넷</b><br>① 아래 <b>메뉴(≡)</b> → ② <b>현재 페이지 추가</b> → ③ <b>홈 화면</b>`;
  return `<b>크롬</b><br>① 오른쪽 위 <b>메뉴(⋮)</b> → ② <b>홈 화면에 추가</b>(또는 <b>앱 설치</b>) → ③ <b>설치/추가</b><br>
    <small>메뉴에 없으면 페이지를 새로고침한 뒤 다시 확인해 주세요.</small>`;
}
function installChip() {                          // 홈 화면 위쪽에 "앱으로 설치" 버튼
  const standalone = matchMedia('(display-mode: standalone)').matches || navigator.standalone;
  if (standalone || !isMobile()) return '';
  return `<button class="installchip" id="installChip">📲 홈 화면에 앱 아이콘 추가</button>`;
}

function initMobile() {
  inAppBanner();
  initSheet();
}
