/* ===== 홈 (둘러보기) =====
   검색창 하나 + 업종 아이콘 칩 + 공식 소식 + 가로 추천 묶음
   평점 데이터가 없으므로 추천은 가격·거리·영업·시설 같은 사실 기준으로만 묶는다.
*/
const HOME = { upjong: '', sub: '' };
const HOME_CATS = [
  ['', '전체', '🧭'], ['한식', '한식', '🍚'], ['중식', '중식', '🥟'], ['일식', '일식', '🍣'],
  ['양식', '양식', '🍝'], ['카페·빵', '카페·빵', '☕'], ['미용·이발', '미용·이발', '✂️'], ['생활', '생활', '🧺'],
];
const FOOD_UJ = ['한식', '중식', '일식', '양식', '카페·빵'];          // 음식점류 (업종 칩 값 기준)
const isFoodItem = i => FOOD_UJ.includes(groupOf(i.u));
const NOTICE_URL = 'https://www.goodprice.go.kr/cmnt/boardList.do?bbsId=BBSCTT_00101';
let LIVE_NOTICES = null;
async function loadNotices() {
  try {
    const d = await (await fetch('/api/notices')).json();
    if (d.items && d.items.length) LIVE_NOTICES = d.items;
  } catch (e) { /* 고정 문구 사용 */ }
}
const noticeIcon = t => /카드|할인|혜택|원/.test(t) ? '💳' : /이벤트|당첨/.test(t) ? '🎁' : /보호|센터/.test(t) ? '📬' : '📢';
function topNotice() {
  if (!LIVE_NOTICES) return null;                          // 수집 실패 시 표시하지 않음
  const n = LIVE_NOTICES[0]; return { t: n.title, d: n.date, icon: noticeIcon(n.title) };
}

/* 홈 기준점: 사용자가 정한 위치 → 선택 시군구 중심 → 시도 전체 중심 */
function homeRef() {
  if (S.my) return { ...S.my, label: S.refLabel || '지정한 위치' };
  const pool = S.sgg ? S.items.filter(inSgg) : S.items;
  if (!pool.length) return null;
  const y = pool.reduce((a, i) => a + i.y, 0) / pool.length;
  const x = pool.reduce((a, i) => a + i.x, 0) / pool.length;
  const sido = S.meta.sido.find(s => s.code === S.sido)?.name || '';
  return { y, x, label: S.sgg ? `${sido.replace(/(특별시|광역시|특별자치시|특별자치도)$/, '')} ${sggName(S.sgg)}` : sido, center: true };
}

function homeCard(it, badge) {
  return `<div class="hc" data-id="${it.i}">
    <div class="hc-ph">${upIcon(it.u)}${it.img ? `<img decoding="async" data-src="${thumb(it)}" alt="" onload="this.classList.add('ok')" onerror="this.remove()">` : ''}
      ${badge ? `<span class="hc-badge ${badge.cls || ''}">${badge.t}</span>` : ''}</div>
    ${(m => m ? `<div class="hc-pr">${won(m[1])}<small>원</small><span>${m[0]}</span></div>` : '')(repMenu(it))}
    <div class="hc-nm">${it.n}</div>
    <div class="hc-mt">${it._hd != null ? fmtDist(it._hd) + ' · ' : ''}${catLabel(it)}</div>
  </div>`;
}

function homeSection(key, title, sub, list, badgeFn) {
  if (!list.length) return '';
  return `<section class="hsec">
    <div class="hsec-h"><div><h3>${title}</h3><small>${sub}</small></div>
      <span class="harr"><button data-harr="prev" aria-label="이전">‹</button><button data-harr="next" aria-label="다음">›</button></span>
      <button class="hmore" data-sec="${key}" aria-label="${title} 전체 보기">→</button></div>
    <div class="hrail">${list.slice(0, 10).map(it => homeCard(it, badgeFn && badgeFn(it))).join('')}</div>
  </section>`;
}

/* 섹션별 조건 — '→'를 누르면 같은 조건을 지도 화면에 적용 */
function sectionDefs(base, ref, ujLabel) {
  const pre = ujLabel ? ujLabel + ' ' : '';
  const isFood = !HOME.upjong || FOOD_UJ.includes(HOME.upjong);
  const byDist = arr => ref ? [...arr].sort((a, b) => a._hd - b._hd) : arr;
  const menuCnt = {};
  const menuBase = HOME.upjong ? base : base.filter(isFoodItem);   // 전체 = 음식점류 기준
  menuBase.forEach(it => it.m.forEach(m => {
    const k = (m[0] || '').replace(/\(.*?\)|\d+.*$/g, '').trim();
    if (k.length >= 2 && k.length <= 6) menuCnt[k] = (menuCnt[k] || 0) + 1;
  }));
  const top = Object.entries(menuCnt).sort((a, b) => b[1] - a[1])[0];
  const area = ref ? ref.label : '';
  const defs = [];
  const cheap = isFood ? 5000 : 10000;
  defs.push({ key: 'cheap', title: `${pre}${won(cheap)}원 이하${isFood ? ' 한 끼' : ''}`, sub: `${area} 가까운 순`,
    list: byDist(base.filter(i => (m => m && m[1] <= cheap)(repMenu(i)) && (HOME.upjong || isFoodItem(i)))),   // 대표 메뉴 기준(곁메뉴로 묶이지 않게)
    apply: { maxPrice: cheap, upjong: HOME.upjong || (isFood ? '' : HOME.upjong) } });
  defs.push({ key: 'open', title: `지금 영업 중인 ${pre || '곳'}`.trim(), sub: '영업시간 등록 업소 기준 · 가까운 순',
    list: byDist(base.filter(i => isOpenNow(i) === true)), badge: () => ({ t: '영업중', cls: 'open' }),
    apply: { quick: ['open'] } });
  if (top && top[1] >= 3) defs.push({ key: 'menu', title: `${area ? area.split(' ').pop() + '에서 ' : ''}많은 메뉴: ${top[0]}`,
    sub: `착한가격 ${top[1]}곳`, list: byDist(menuBase.filter(i => i.m.some(m => (m[0] || '').includes(top[0])))),
    apply: { keyword: top[0] } });
  defs.push({ key: 'pack', title: `포장 되는 ${pre || '곳'}`.trim(), sub: '가져가서 먹기 좋은 곳',
    list: byDist(base.filter(i => i.f.includes('포장'))), badge: () => ({ t: '포장' }), apply: { fac: ['포장'] } });
  defs.push({ key: 'park', title: `주차 되는 ${pre || '곳'}`.trim(), sub: '차로 가기 편한 곳',
    list: byDist(base.filter(i => i.f.includes('주차'))), badge: () => ({ t: '주차' }), apply: { fac: ['주차'] } });
  if (!HOME.upjong) defs.push({ key: 'hair', title: '미용·이발', sub: '커트·파마 착한가격',
    list: byDist(base.filter(i => groupOf(i.u) === '미용·이발')), apply: { upjong: '미용·이발' } });
  return defs;
}

function renderHome() {
  const el = $('#home'); if (!el) return;
  const ref = homeRef();
  let base = S.items.filter(inSgg);
  if (HOME.upjong) base = base.filter(i => matchCat(i, HOME.upjong, HOME.sub));
  base.forEach(i => { i._hd = ref ? dist(ref.y, ref.x, i.y, i.x) : null; });
  // 사진 있는 곳을 우선 노출(둘러보기 화면이므로)
  base = [...base].sort((a, b) => (b.img ? 1 : 0) - (a.img ? 1 : 0));

  const defs = sectionDefs(base, ref, HOME.upjong ? ujText(HOME.upjong, HOME.sub) : '');
  HOME._defs = defs;
  const subs = HOME.upjong && subList(HOME.upjong);

  el.innerHTML = `
    <div class="home-top">
      <div class="home-brand">
        <img class="only-light" src="assets/logo-pill.png" alt="착한가격"><img class="only-dark" src="assets/logo-pill-dark.png" alt="착한가격">
        <div><b>지도</b><span>행정안전부 착한가격업소 공공데이터 기반</span></div>
        <button class="icobtn vsbtn" id="homeTheme" aria-label="보기 설정(화면 밝기·글씨 크기)" title="보기 설정"><span aria-hidden="true">가</span></button>
      </div>
      ${typeof installChip === 'function' ? installChip() : ''}
      <button class="home-loc" id="homeLoc">📍 <b>${ref ? ref.label : '지역을 선택하세요'}</b> ${ref && ref.center ? '중심' : ''} 기준 <span>변경 ›</span></button>
      <button class="home-search" id="homeSearch">
        <svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/></svg>
        <span><b>어디서 뭘 찾으세요?</b><small>지역 · 메뉴 · 가격 · 문장으로 검색</small></span>
      </button>
    </div>
    <nav class="home-cats">${HOME_CATS.map(([v, t, ic]) =>
      `<button class="hcat ${HOME.upjong === v ? 'on' : ''}" data-uj="${v}"><span>${ic}</span>${t}</button>`).join('')}</nav>
    ${subs ? `<nav class="home-subs">${[['', '전체'], ...subs].map(([s, t]) =>
      `<button class="chip sub-chip" aria-pressed="${HOME.sub === s}" data-sub="${s}">${t}</button>`).join('')}</nav>` : ''}
    ${(n => n ? `<a class="home-notice" href="${NOTICE_URL}" target="_blank" rel="noopener">
      <span class="ni">${n.icon}</span>
      <span class="nt"><b>${n.t}</b><small>공식 소식 · ${n.d || ''}</small></span><span class="na">›</span>
    </a>` : '')(topNotice())}
    ${defs.map(d => homeSection(d.key, d.title, d.sub, d.list, d.badge)).join('') ||
      '<p class="home-empty">이 조건의 업소가 없습니다. 다른 업종을 골라보세요.</p>'}
    <button class="home-mapbtn" id="homeMap">🗺 지도에서 전체 보기 (${base.length.toLocaleString()}곳)</button>
    <p class="home-foot">자료: 행정안전부 착한가격업소(goodprice.go.kr), 공공데이터포털<br>개인이 공공데이터로 만든 비공식 서비스입니다.</p>`;
  bindHome();
}

function bindHome() {
  const el = $('#home');
  el.querySelectorAll('.hcat').forEach(b => b.onclick = () => { HOME.upjong = b.dataset.uj; HOME.sub = ''; renderHome(); });
  el.querySelectorAll('[data-sub]').forEach(b => b.onclick = () => { HOME.sub = b.dataset.sub; renderHome(); });
  el.querySelectorAll('.hc').forEach(c => c.onclick = () => {
    const it = S.items.find(i => i.i === c.dataset.id);
    showView('map'); if (it) { apply(); openDetail(it); }
  });
  el.querySelectorAll('.hmore').forEach(b => b.onclick = () => {
    const d = (HOME._defs || []).find(x => x.key === b.dataset.sec); if (!d) return;
    goMapWith(d.apply || {});
  });
  $('#homeMap').onclick = () => goMapWith({});
  $('#homeSearch').onclick = () => {
    sessionStorage.removeItem('introSeen');
    runIntro({ meta: S.meta, items: () => S.items, applyParsed: async p => { const n = await applyParsed(p); showView('map'); return n; } });
  };
  $('#homeLoc').onclick = () => goMapWith({}, true);
  if ($('#installChip')) $('#installChip').onclick = installApp;
  $('#homeTheme').onclick = openViewSheet;
}

/* 홈 조건을 지도 화면에 적용 */
function goMapWith(a, pickLocation) {
  S.upjong = a.upjong !== undefined ? a.upjong : HOME.upjong;
  S.sub = a.sub !== undefined ? a.sub : (a.upjong === undefined || a.upjong === HOME.upjong) ? HOME.sub : '';
  S.maxPrice = a.maxPrice || null;
  S.quick = new Set(a.quick || []);
  S.fac = new Set(a.fac || []);
  $('#q').value = a.keyword || ''; $('#qclear').hidden = !a.keyword;
  $('#priceChip').textContent = (S.maxPrice ? won(S.maxPrice) + '원 이하' : '가격') + ' ▾';
  $('#priceChip').classList.toggle('on', !!S.maxPrice);
  document.querySelectorAll('[data-quick]').forEach(b => b.classList.toggle('on', S.quick.has(b.dataset.quick)));
  renderChips(); renderSub(); filterCount();
  if (!S.my) { const r = homeRef(); if (r) S.center = { y: r.y, x: r.x }; }
  showView('map'); apply(); fitMap();
  if (pickLocation) $('#pinBtn').click();
}

/* 화면 전환: home ↔ map */
function showView(v) {
  document.body.dataset.view = v;
  if (v === 'home') renderHome();
  if (v === 'saved' || v === 'recent') renderList2(v);
  if (v === 'more') renderMore();
  if (v !== 'map' && v !== 'home') $('#pageView').scrollTop = 0;
  if (v === 'map' && S.map) setTimeout(() => {
    S.map.relayout();                        // 숨겨진 상태에서 만들어진 지도 크기 보정
    if (!S.sel) fitMap();                    // 선택 업소가 없으면 현재 결과에 맞춰 이동
  }, 60);
  if (typeof renderTabbar === 'function') renderTabbar();
}
