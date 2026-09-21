/* ===== 인트로 + 대화형 시작 화면 =====
   외부 AI API 없이 자체 데이터(지역명·메뉴명·업종·조건)로 문장을 해석한다.
*/
const INTRO = {
  greet: ['안녕하세요! 👋', '어디서 무엇을 찾고 계신가요?'],
  samples: ['강남에서 5천원 이하 점심', '종로구 칼국수', '내 주변 김밥', '부산 미용실 지금 영업중'],
};

/* 지역 사전: 시도 → 시군구 (index.json) + 행정동은 로드된 데이터에서 탐색 */
const SIDO_ALIAS = {   // 사람들이 흔히 쓰는 줄임말
  '11': ['서울'], '26': ['부산'], '27': ['대구'], '28': ['인천'], '30': ['대전'], '31': ['울산'], '36': ['세종'],
  '41': ['경기'], '51': ['강원'], '43': ['충북', '충청북도'], '44': ['충남', '충청남도'], '52': ['전북', '전라북도'],
  '12': ['광주', '전남', '전라남도', '광주광역시'], '47': ['경북', '경상북도'], '48': ['경남', '경상남도'], '50': ['제주'],
};
function buildRegionDict(meta) {
  const dict = [];
  meta.sido.forEach(s => {
    const short = s.name.replace(/(특별시|광역시|특별자치시|특별자치도|도)$/, '');
    dict.push({ type: 'sido', code: s.code, name: s.name, keys: [...new Set([s.name, short, ...(SIDO_ALIAS[s.code] || [])])] });
    (s.sgg || []).forEach(g => dict.push({
      type: 'sgg', code: s.code, name: g, sido: s.name,
      keys: [g, g.replace(/(시|군|구|읍|면)$/, '')].filter(k => k.length >= 2),
    }));
  });
  return dict;
}

const PRICE_WORDS = [
  [/([1-9]\d?)\s*만\s*([1-9])\s*천\s*원?\s*(이하|이내|밑|아래|까지)?/, m => +m[1] * 10000 + +m[2] * 1000],   // 1만5천원
  [/([1-9]\d?)\s*만\s*원?\s*(이하|이내|밑|아래|까지)/, m => +m[1] * 10000],
  [/([1-9])\s*천\s*원?\s*(이하|이내|밑|아래|까지)/, m => +m[1] * 1000],
  [/([1-9]\d{2,5})\s*원?\s*(이하|이내|밑|아래|까지)/, m => +m[1]],
  [/만\s*원?\s*(이하|이내|밑|아래|까지)/, () => 10000],
  [/천\s*원?\s*(이하|이내|밑|아래|까지)/, () => 1000],
  [/(싼|저렴|가성비|혜자)/, () => 5000],
];
const UPJONG_WORDS = {
  한식: ['한식', '백반', '국밥', '찌개', '김치', '비빔밥', '삼겹', '갈비', '분식', '김밥', '떡볶이', '국수', '칼국수', '냉면', '순대', '한정식', '해산물'],
  중식: ['중식', '중국집', '짜장', '짬뽕', '탕수육'],
  일식: ['일식', '초밥', '스시', '돈까스', '우동', '물회', '모둠회', '모듬회', '생선회', '회덮밥'],
  양식: ['양식', '파스타', '피자', '스테이크'],
  베이커리: ['베이커리', '빵집', '제과'],
  기타요식업: ['카페', '커피', '디저트'],
  미용업: ['미용', '미용실', '헤어', '파마', '염색', '커트', '컷'],
  이용업: ['이용원', '이발', '이발소', '바버'],
  세탁업: ['세탁', '빨래', '드라이클리닝'],
  목욕업: ['목욕', '사우나', '찜질'],
  숙박업: ['숙박', '모텔', '여관', '호텔'],
};
const COND_WORDS = [
  [/지금|영업\s*중|문\s*연|오픈/, 'open'],
  [/사진/, 'photo'],
  [/주차/, 'fac:주차'], [/배달/, 'fac:배달'], [/포장|테이크아웃/, 'fac:포장'],
  [/반려|애견|강아지/, 'fac:반려동물'], [/단체|회식/, 'fac:단체가능'],
  [/와이파이|wifi/i, 'fac:와이파이'], [/유아|아기|아이(?!스)/, 'fac:유아시설'],
  [/장애인|휠체어/, 'fac:장애인시설'], [/지역화폐|상품권/, 'fac:지역화폐'],
];
const CATEGORY_WORDS = new Set([
  '한식', '중식', '중국집', '일식', '양식', '베이커리', '빵집', '제과', '카페',
  '미용', '미용실', '헤어', '이용원', '이발', '이발소', '바버',
  '세탁', '빨래', '목욕', '사우나', '찜질', '숙박', '모텔', '여관', '호텔']);
/* 동의어·오타 정규화: 입력을 표준 표기로 바꾼 뒤 해석한다 */
const NORMALIZE = [
  [/자장면/g, '짜장면'], [/돈가스|돈카츠|돈까스/g, '돈까스'], [/칼국쑤|칼국시/g, '칼국수'],
  [/헤어샵|헤어샾|미용원/g, '미용실'], [/이발관|바버샵/g, '이발소'], [/빨래방|세탁소/g, '세탁'],
  [/커피숍|커피샵|카페테리아/g, '카페'], [/떡복이|떡뽁이/g, '떡볶이'], [/찌게/g, '찌개'],
  [/순두부찌개|순대국밥/g, '국밥'], [/고깃집|고기집|삼겹살집/g, '삼겹'], [/막국수|잔치국수/g, '국수'],
];
/* 상황어: 사람이 쓰는 말 → 검색 조건 */
const SITUATION = [
  [/해장/, { upjong: '한식', keyword: '국밥' }],
  [/국물|따뜻한|뜨끈/, { upjong: '한식', keyword: '찌개' }],
  [/혼밥|혼자/, { upjong: '한식' }],
  [/회식|모임|단체/, { conds: ['fac:단체가능'] }],
  [/아침|조식/, { conds: ['open'] }],
  [/야식|밤늦게/, { conds: ['open'] }],
  [/아이(?!스)|애기|유아|가족/, { conds: ['fac:유아시설'] }],
  [/차\s*가지고|드라이브|주차/, { conds: ['fac:주차'] }],
  [/고기|구이/, { upjong: '한식', keyword: '삼겹' }],
  [/면\s*요리|면류/, { upjong: '한식', keyword: '국수' }],
  [/머리|커트|자르/, { upjong: '미용업' }],
];
const NEAR_WORDS = /내\s*주변|근처|주변|가까운|내\s*위치/;

/* 검색어가 앱의 세부분류(한정식·분식·면류 등)와 같으면 메뉴 검색 대신 세부분류로 적용
   ('한정식'을 메뉴 이름에서 찾으면 0곳이 되는 문제) */
function keywordToSub(p) {
  const subs = (typeof SUBS !== 'undefined' && SUBS['한식']) || [];
  if (p.keyword && subs.includes(p.keyword)) { p.upjong = '한식'; p.sub = p.keyword; p.keyword = ''; }
  return p;
}

/* 문장 해석 */
function parseQuery(text, dict, items) {
  let t = text.trim();
  NORMALIZE.forEach(([re, to]) => { t = t.replace(re, to); });
  const out = { region: null, dong: null, upjong: '', keyword: '', maxPrice: null, conds: [], near: false };

  // 지역: 시도가 함께 나오면 그 시도 안의 시군구만 인정 (부산 중구 ≠ 서울 중구, 광주 ≠ 경기 광주시)
  const klen = d => Math.max(...d.keys.filter(k => t.includes(k)).map(k => k.length));
  const hitSido = dict.filter(d => d.type === 'sido' && d.keys.some(k => t.includes(k))).sort((a, b) => klen(b) - klen(a));
  const hitSgg = dict.filter(d => d.type === 'sgg' && d.keys.some(k => t.includes(k))).sort((a, b) => klen(b) - klen(a));
  if (hitSido.length) {
    // '제주 국수'처럼 시도 이름과 같은 글자로만 잡힌 시군구(제주시)는 제외 → 시도 전체
    out.region = hitSgg.find(g => {
      const own = hitSido.find(s => s.code === g.code);
      return own && g.keys.some(k => t.includes(k) && !own.keys.includes(k));
    }) || hitSido[0];
  } else if (hitSgg.length) {
    // 같은 이름의 시군구가 여러 시도에 있으면 지금 보고 있는 시도를 우선
    const cur = typeof S !== 'undefined' ? S.sido : '';
    out.region = hitSgg.find(g => g.code === cur && klen(g) === klen(hitSgg[0])) || hitSgg[0];
  }

  // 행정동 (현재 로드된 시도 기준)
  const dong = [...new Set(items.map(i => i.e).filter(Boolean))].find(e => e && t.includes(e));
  if (dong) out.dong = dong;

  // 가격
  for (const [re, fn] of PRICE_WORDS) { const m = t.match(re); if (m) { out.maxPrice = fn(m); break; } }

  // 업종·메뉴 (긴 단어 우선 → '칼국수'가 '국수'보다 먼저 매칭)
  let best = null;
  for (const [uj, words] of Object.entries(UPJONG_WORDS)) {
    for (const w of words) {
      if (t.includes(w) && (!best || w.length > best.w.length)) best = { uj, w };
    }
  }
  if (best) {
    out.upjong = best.uj;
    if (!CATEGORY_WORDS.has(best.w)) out.keyword = best.w;
  }
  // 조건
  COND_WORDS.forEach(([re, c]) => { if (re.test(t)) out.conds.push(c); });
  out.near = NEAR_WORDS.test(t);

  // 상황어 보완 (명시 조건이 없을 때만 채움)
  for (const [re, add] of SITUATION) {
    if (!re.test(t)) continue;
    if (add.upjong && !out.upjong) out.upjong = add.upjong;
    if (add.keyword && !out.keyword) out.keyword = add.keyword;
    if (add.conds) add.conds.forEach(c => { if (!out.conds.includes(c)) out.conds.push(c); });
  }
  out.conds = [...new Set(out.conds)];
  keywordToSub(out);

  // 해석 신뢰도: 아무것도 못 읽었으면 낮음 → AI 폴백 대상
  out.hits = (out.region ? 1 : 0) + (out.dong ? 1 : 0) + (out.upjong ? 1 : 0) +
             (out.keyword ? 1 : 0) + (out.maxPrice ? 1 : 0) + out.conds.length + (out.near ? 1 : 0);
  return out;
}

function describe(p, count) {
  const bits = [];
  if (p.near) bits.push('현재 위치 주변');
  if (p.region) bits.push(p.region.type === 'sgg' ? `${p.region.sido} ${p.region.name}` : p.region.name);
  if (p.dong) bits.push(p.dong);
  if (p.upjong) bits.push(p.sub ? `${p.upjong}·${p.sub}` : p.upjong);
  if (p.keyword) bits.push(`'${p.keyword}'`);
  if (p.maxPrice) bits.push(`${p.maxPrice.toLocaleString()}원 이하`);
  p.conds.forEach(c => bits.push(c === 'open' ? '지금 영업중' : c === 'photo' ? '사진 있음' : c.slice(4)));
  const relaxed = p.relaxed && p.relaxed.length
    ? `<br><small>${p.relaxed.join(', ')} 조건으로는 없어서 그 조건을 빼고 찾았어요.</small>` : '';
  return `${bits.join(' · ') || '전체'} 조건으로 <b>${count.toLocaleString()}곳</b>을 찾았어요.${relaxed}`;
}

/* 화면 */
function introHTML() {
  return `
  <div class="intro" id="intro">
    <img class="intro-wm only-light" src="assets/logo-circle.png" alt="">
    <img class="intro-wm only-dark" src="assets/logo-circle-dark.png" alt="">
    <div class="intro-emblem">
      <img class="intro-logo only-light" src="assets/logo-circle.png" alt="착한가격">
      <img class="intro-logo only-dark" src="assets/logo-circle-dark.png" alt="착한가격">
      <div class="intro-name">착한가격 지도</div>
      <p class="emblem-note">행정안전부 착한가격업소 공공데이터 기반<small>개인이 공공데이터로 만든 비공식 서비스</small></p>
    </div>
    <div class="intro-chat" id="introChat">
      <div class="bubbles" id="bubbles">
        ${INTRO.greet.map((g, i) => `<div class="bubble bot" style="animation-delay:${.15 * i + .5}s">${g}</div>`).join('')}
      </div>
      <div class="samples">${INTRO.samples.map(s => `<button class="chip">${s}</button>`).join('')}</div>
      <form class="askbar" id="askForm">
        <input id="ask" placeholder="예: 강남에서 5천원 이하 점심" autocomplete="off">
        <button class="askgo" type="submit" aria-label="검색">→</button>
      </form>
      <button class="skip" id="skip">둘러보기 →</button>
    </div>
  </div>`;
}

/* AI 폴백 — 서버(/api/parse)를 통해서만 호출한다(키 비노출) */
async function aiParse(text, dict) {
  const ctl = new AbortController(), timer = setTimeout(() => ctl.abort(), 8000);   // 8초 넘으면 규칙 해석으로
  const r = await fetch('/api/parse', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }), signal: ctl.signal,
  }).finally(() => clearTimeout(timer));
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).error || 'AI 오류');
  const { source, parsed } = await r.json();
  // AI가 준 조건 → 앱 내부 형식으로 변환
  // AI 답은 그대로 믿지 않고 앱에 있는 값만 사용
  const sido = parsed.sido ? dict.find(d => d.type === 'sido' && (d.name === parsed.sido || d.keys.includes(parsed.sido))) : null;
  const sggs = parsed.sgg ? dict.filter(d => d.type === 'sgg' && d.name === parsed.sgg) : [];
  const region = (sido ? sggs.find(g => g.code === sido.code) : sggs[0]) || sido || null;
  const FACS = ['주차', '포장', '배달', '예약', '단체가능', '와이파이', '반려동물', '유아시설', '장애인시설', '임산부우대', '지역화폐', '남녀화장실'];
  const UJ = ['한식', '중식', '일식', '양식', '베이커리', '기타요식업', '미용업', '이용업', '세탁업', '목욕업', '숙박업', '기타비요식업'];
  if (!UJ.includes(parsed.upjong)) parsed.upjong = '';
  const conds = (parsed.facilities || []).filter(f => FACS.includes(f)).map(f => 'fac:' + f);
  if (parsed.openNow) conds.push('open');
  return keywordToSub({
    source, region, dong: null, upjong: parsed.upjong || '', keyword: parsed.keyword || '',
    maxPrice: parsed.maxPrice > 0 && parsed.maxPrice < 1e6 ? parsed.maxPrice : null, conds, near: !!parsed.near, hits: 9,
  });
}

async function runIntro(ctx) {
  document.body.insertAdjacentHTML('afterbegin', introHTML());
  const dict = buildRegionDict(ctx.meta);
  const close = () => { const el = $('#intro'); el.classList.add('out'); setTimeout(() => el.remove(), 320); };
  $('#skip').onclick = close;
  document.querySelectorAll('.samples .chip').forEach(b => b.onclick = () => { $('#ask').value = b.textContent; $('#askForm').requestSubmit(); });

  $('#askForm').onsubmit = async e => {
    e.preventDefault();
    const text = $('#ask').value.trim(); if (!text) return;
    const me = document.createElement('div'); me.className = 'bubble me'; me.textContent = text;   // 입력 글자는 그대로 표시(태그 해석 안 함)
    $('#bubbles').appendChild(me);
    $('#ask').value = '';
    let p = parseQuery(text, dict, ctx.items());
    let note = '';
    if (p.hits === 0) {                       // 규칙으로 아무것도 못 읽음 → AI에게 넘김
      $('#bubbles').insertAdjacentHTML('beforeend', '<div class="bubble bot" id="thinking">잠시만요, 문장을 이해하는 중이에요…</div>');
      try {
        const ai = await aiParse(text, dict);
        p = ai; note = ` <span class="src-ai">${ai.source === 'gemini' ? 'AI 해석' : 'AI 해석(보조)'}</span>`;
      } catch (err) {
        document.getElementById('thinking')?.remove();
        $('#bubbles').insertAdjacentHTML('beforeend',
          '<div class="bubble bot">잘 이해하지 못했어요. 지역·메뉴·가격을 넣어 다시 말씀해 주세요.<br>예) 강남 김밥 5천원 이하</div>');
        return;
      }
      document.getElementById('thinking')?.remove();
    }
    const count = await ctx.applyParsed(p);
    $('#bubbles').insertAdjacentHTML('beforeend', `<div class="bubble bot">${describe(p, count)}${note}</div>`);
    $('#bubbles').scrollTop = 1e6;
    setTimeout(close, 900);
  };
}
