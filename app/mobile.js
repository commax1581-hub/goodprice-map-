/* ===== 휴대폰 사용성 =====
   - 카카오톡 등 앱 안 브라우저 안내(홈 화면 추가·위치가 제한됨 → 기본 브라우저로 열기)
   - 목록 시트 3단계(작게·중간·크게), 지도 끌면 목록 자동으로 작게
   - 내 위치(GPS) → 그 위치의 시도·시군구(세종은 읍면동)로 자동 전환
   - 카카오톡으로 공유(카카오 공식 공유 기능)
   - 홈 화면에 추가(설치): 브라우저별 안내, 홈 첫 화면 버튼, 업소를 본 뒤 한 번 제안(7일간 다시 안 띄움)
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
      res({ sido: h.region_1depth_name, sgg: h.region_2depth_name, dong: h.region_3depth_name });
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
  // 시군구: 데이터의 시군구 이름과 맞춰 선택 (수원시 장안구 → 수원시, 세종은 읍면동)
  const names = [...new Set(S.items.map(i => i.g))];
  const want = code === '36' ? rg.dong : rg.sgg;
  const g = names.filter(n => want === n || want.startsWith(n + ' ')).sort((a, b) => b.length - a.length)[0];
  S.sgg = g || '';
  renderSgg(); $('#selSgg').value = S.sgg;
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
function browserName() {
  if (IN_APP === 'kakao') return '카카오톡 안 브라우저';
  if (/NAVER\(inapp/i.test(UA)) return '네이버 앱 안 브라우저';
  if (IN_APP) return '앱 안 브라우저';
  if (/Whale/i.test(UA)) return '네이버 웨일';
  if (/SamsungBrowser/i.test(UA)) return '삼성 인터넷';
  if (/EdgA|Edg\//i.test(UA)) return '엣지';
  if (/Firefox|FxiOS/i.test(UA)) return '파이어폭스';
  if (IS_IOS && /CriOS/i.test(UA)) return '크롬(아이폰)';
  if (IS_IOS) return '사파리';
  if (/Chrome/i.test(UA)) return '크롬';
  return '';
}
function installGuideHTML() {
  const b = browserName(), head = b ? `<p class="gb-b">사용 중인 브라우저: <b>${b}</b></p>` : '';
  const step = s => head + s;
  if (IN_APP) return step(`지금은 앱 안에서 열려 있어 추가할 수 없어요.<br>아래 버튼으로 기본 브라우저에서 연 뒤 다시 눌러 주세요.
    <br><button class="chip" id="gbExt">브라우저로 열기</button>`);
  if (IS_IOS && !/CriOS|FxiOS|EdgiOS/i.test(UA)) return step(`① 화면 아래 <b>공유 버튼(□↑)</b><br>② <b>홈 화면에 추가</b><br>③ 오른쪽 위 <b>추가</b>`);
  if (IS_IOS) return step(`아이폰에서는 <b>사파리</b>에서만 홈 화면에 추가할 수 있어요.<br>주소를 복사해 사파리에서 연 뒤 공유(□↑) → 홈 화면에 추가`);
  if (/Whale/i.test(UA)) return step(`① 화면 아래 <b>메뉴(≡)</b><br>② <b>홈 화면에 추가</b>(또는 <b>앱 설치</b>)<br>③ <b>추가/설치</b>`);
  if (/SamsungBrowser/i.test(UA)) return step(`① 화면 아래 <b>메뉴(≡)</b><br>② <b>현재 페이지 추가</b><br>③ <b>홈 화면</b>`);
  if (/EdgA/i.test(UA)) return step(`① 아래 <b>메뉴(…)</b><br>② <b>휴대폰에 추가</b>(또는 <b>앱 설치</b>)`);
  if (/Firefox/i.test(UA)) return step(`① 오른쪽 위 <b>메뉴(⋮)</b><br>② <b>설치</b>(또는 <b>홈 화면에 추가</b>)`);
  return step(`① 오른쪽 위 <b>메뉴(⋮)</b><br>② <b>홈 화면에 추가</b>(또는 <b>앱 설치</b>)<br>③ <b>설치/추가</b>
    <br><small>메뉴에 없으면 페이지를 새로고침한 뒤 다시 확인해 주세요.</small>`);
}
const LS = { get: k => { try { return localStorage.getItem(k); } catch (e) { return null; } },
             set: (k, v) => { try { localStorage.setItem(k, v); } catch (e) { } } };
const isInstalled = () => matchMedia('(display-mode: standalone)').matches || navigator.standalone || LS.get('installed') === '1';
addEventListener('appinstalled', () => { LS.set('installed', '1'); document.querySelectorAll('.installchip,.installtoast').forEach(e => e.remove()); });
function installNudge() {                         // 업소를 한 번 본 뒤 아래쪽에 한 번만 제안
  if (!isMobile() || isInstalled() || document.querySelector('.installtoast')) return;
  const snooze = +(LS.get('installSnooze') || 0);
  if (Date.now() < snooze) return;
  LS.set('installSnooze', String(Date.now() + 7 * 864e5));
  document.body.insertAdjacentHTML('beforeend', `<div class="installtoast" role="dialog">
    <img src="assets/icon-192.png" alt=""><span><b>앱처럼 쓰기</b><small>홈 화면에 아이콘을 추가하면 더 크게, 바로 열려요</small></span>
    <button id="itAdd">추가</button><button class="x" id="itX" aria-label="닫기">✕</button></div>`);
  $('#itAdd').onclick = () => { document.querySelector('.installtoast').remove(); installApp(); };
  $('#itX').onclick = () => document.querySelector('.installtoast').remove();
}
function installChip() {                          // 홈 화면 위쪽에 "앱으로 설치" 버튼
  if (isInstalled() || !isMobile()) return '';
  return `<button class="installchip" id="installChip">📲 홈 화면에 앱 아이콘 추가</button>`;
}

function initMobile() {
  if (LS.get('installed') !== '1' && (matchMedia('(display-mode: standalone)').matches || navigator.standalone)) LS.set('installed', '1');
  inAppBanner();
  initSheet();
}
