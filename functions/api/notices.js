/* 공식 소식 (server.py의 /api/notices를 옮김)
   공식 누리집 공지 목록에서 제목·날짜만 읽는다(본문·이미지·이용후기는 수집하지 않음).
   공식 사이트에는 하루 1회 수준으로만 요청되도록 Cloudflare 캐시에 24시간 보관한다. */
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

export async function onRequestGet({ request, waitUntil }) {
  const cache = caches.default;
  const key = new Request(new URL('/api/notices', request.url).toString());
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
    body = { fetched_at: 0, source: NOTICE_URL, items: [], error: e.name };   // 실패 시 화면은 숨김 처리
  }
  const res = new Response(JSON.stringify(body), { headers: {
    'Content-Type': 'application/json; charset=utf-8',
    'Cache-Control': `public, max-age=${body.items.length ? TTL : 600}` } });
  waitUntil(cache.put(key, res.clone()));
  return res;
}
