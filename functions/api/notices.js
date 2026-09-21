/* 공식 소식 (server.py의 /api/notices를 옮김)
   공식 누리집 공지 목록에서 제목·날짜만 읽는다(본문·이미지·이용후기는 수집하지 않음).
   공식 사이트에는 하루 1회 수준으로만 요청되도록 Cloudflare 캐시에 24시간 보관한다.
   ※ 공식 누리집이 클라우드 접속을 막는 경우가 있어, 실패하면 app/data/notices.json(PC에서 수집)을 쓴다. */
const NOTICE_URL = 'https://www.goodprice.go.kr/cmnt/boardList.do?bbsId=BBSCTT_00101';
const TTL = 24 * 3600;

const unescape = s => s.replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>')
  .replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&nbsp;/g, ' ');

function parse(page) {
  const items = [];
  for (const [, row] of page.matchAll(/<tr>([\s\S]*?)<\/tr>/g)) {
    const m = row.match(/goInfo\('(\d+)'\);">\s*([\s\S]*?)\s*<\/a>[\s\S]*?<td>[^<]*<\/td>\s*<td>(\d{4}-\d{2}-\d{2})<\/td>/);
    if (!m) continue;
    items.push({ id: m[1], title: unescape(m[2].replace(/<[^>]+>/g, '').replace(/\s+/g, ' ')).trim(),
                 date: m[3], pinned: row.includes('notice_display') });
  }
  const byDate = (a, b) => b.date.localeCompare(a.date);
  return [...items.filter(i => i.pinned).sort(byDate), ...items.filter(i => !i.pinned).sort(byDate)].slice(0, 6);
}

export async function onRequestGet({ request, env, waitUntil }) {
  const cache = caches.default;
  const key = new Request(new URL('/api/notices?v=2', request.url).toString());   // 캐시 구분(형식 바뀌면 숫자 올림)
  const hit = await cache.match(key);
  if (hit) return hit;

  let body;
  try {
    const r = await fetch(NOTICE_URL, {
      headers: { 'User-Agent': 'Mozilla/5.0 (personal-study; goodprice map mashup)' },
      cf: { cacheTtl: TTL, cacheEverything: true },          // 원본 요청도 하루 보관
    });
    body = { fetched_at: Date.now() / 1000, source: NOTICE_URL, items: r.ok ? parse(await r.text()) : [] };
  } catch (e) {
    body = { fetched_at: 0, source: NOTICE_URL, items: [] };
  }
  // 공식 누리집이 클라우드 접속을 막아 실시간 수집이 안 되면 → PC에서 받아 함께 올린 목록 사용(update_notices.py)
  if (!body.items.length) {
    try {
      const saved = await (await env.ASSETS.fetch(new URL('/data/notices.json', request.url))).json();
      if (saved.items && saved.items.length) body = { ...saved, bundled: true };
    } catch (e) { /* 둘 다 없으면 화면에서 숨김 처리 */ }
  }
  const res = new Response(JSON.stringify(body), { headers: {
    'Content-Type': 'application/json; charset=utf-8',
    'Cache-Control': `public, max-age=${body.items.length ? TTL : 600}` } });
  waitUntil(cache.put(key, res.clone()));
  return res;
}
