/* 문장 해석 중계 (server.py의 /api/parse를 Cloudflare Pages Functions로 옮김)
   제미나이 키는 Cloudflare 환경변수 GEMINI_KEY에만 두고 브라우저로 보내지 않는다.
   AI 응답 검증(허용 업종·시설만 사용)은 화면 쪽 intro.js의 aiParse에서 한다. */
const MODEL = 'gemini-3.1-flash-lite';

const SYSTEM = `한국 착한가격업소 검색 앱의 질의 해석기다. 사용자 문장을 검색 조건 JSON으로만 변환하라.
- upjong은 다음 중 하나: 한식,중식,일식,양식,베이커리,기타요식업,미용업,이용업,세탁업,목욕업,숙박업,기타비요식업
- keyword는 구체적 메뉴명(예: 김밥,칼국수,커트). 없으면 빈 문자열
- facilities는 다음에서만 고른다: 주차,포장,배달,예약,단체가능,와이파이,반려동물,유아시설,장애인시설,임산부우대,지역화폐,남녀화장실
- sido/sgg는 한국 행정구역 정식 명칭(예: 부산광역시, 해운대구)
- 해당 없으면 빈 문자열 / 0 / false`;

const SCHEMA = { type: 'object', properties: {
  sido: { type: 'string' }, sgg: { type: 'string' }, upjong: { type: 'string' },
  keyword: { type: 'string' }, maxPrice: { type: 'integer' },
  facilities: { type: 'array', items: { type: 'string' } },
  openNow: { type: 'boolean' }, near: { type: 'boolean' } } };

const json = (obj, status = 200) => new Response(JSON.stringify(obj), {
  status, headers: { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store' } });

export async function onRequestPost({ request, env }) {
  let text = '';
  try { text = String((await request.json()).text || '').trim().slice(0, 200); }
  catch (e) { return json({ error: 'bad request' }, 400); }
  if (!text) return json({ error: 'empty' }, 400);
  if (!env.GEMINI_KEY) return json({ error: 'AI 해석 실패', detail: ['gemini: 키 없음'] }, 502);

  const url = `https://generativelanguage.googleapis.com/v1beta/models/${env.GEMINI_MODEL || MODEL}:generateContent`;
  try {
    const call = () => fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'x-goog-api-key': env.GEMINI_KEY },
      body: JSON.stringify({
        systemInstruction: { parts: [{ text: SYSTEM }] },
        contents: [{ parts: [{ text }] }],
        generationConfig: { responseMimeType: 'application/json', responseSchema: SCHEMA, temperature: 0 },   // 같은 문장 = 같은 해석
      }),
    });
    let r = await call();
    if ([429, 500, 503].includes(r.status)) {                  // 일시 오류(과부하·한도) → 한 번 재시도
      await new Promise(res => setTimeout(res, 800));
      r = await call();
    }
    if (!r.ok) return json({ error: 'AI 해석 실패', detail: [`gemini: HTTP ${r.status}`] }, 502);
    const j = await r.json();
    const parsed = JSON.parse(j.candidates[0].content.parts[0].text);
    return json({ source: 'gemini', parsed });
  } catch (e) {
    return json({ error: 'AI 해석 실패', detail: [`gemini: ${e.name}`] }, 502);
  }
}

export const onRequestGet = () => json({ error: 'POST only' }, 405);
