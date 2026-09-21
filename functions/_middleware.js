/* 공유 미리보기 (server.py의 _send_index를 옮김)
   첫 화면(index.html)을 보낼 때 카카오톡 등 미리보기용 OG 태그를 채운다.
   공유 링크(?s=시도코드&id=관리번호)면 업소 이름·대표 메뉴 가격·주소·축소본 사진을 넣는다. */
const DEFAULT = {
  title: '착한가격 지도',
  desc: '전국 착한가격업소 13,000여 곳을 지도에서 찾아보세요.',
  img: '/assets/og-default.png',
};

class SetContent {
  constructor(v) { this.v = v; }
  element(el) { el.setAttribute('content', this.v); }
}

export async function onRequest({ request, next, env }) {
  const url = new URL(request.url);
  if (request.method !== 'GET' || !(url.pathname === '/' || url.pathname === '/index.html')) return next();

  const res = await next();
  if (!(res.headers.get('content-type') || '').includes('text/html')) return res;

  let { title, desc, img } = DEFAULT;
  const s = url.searchParams.get('s') || '', id = url.searchParams.get('id') || '';
  if (/^\d{2}$/.test(s) && /^GP\d+$/.test(id)) {
    try {
      const data = await (await env.ASSETS.fetch(new URL(`/data/${s}.json`, url))).json();
      const it = data.find(i => i.i === id);
      if (it) {
        const m = it.m && it.m[0];
        title = `${it.n} · 착한가격업소`;
        desc = [m && m[1] != null ? `${m[0]} ${m[1].toLocaleString('ko-KR')}원` : '', it.a || ''].filter(Boolean).join(' · ');
        if (it.img) {
          const th = await env.ASSETS.fetch(new URL(`/thumbs/${it.i}.webp`, url));
          if (th.ok) img = `/thumbs/${it.i}.webp`;
        }
      }
    } catch (e) { /* 기본 미리보기 사용 */ }
  }
  return new HTMLRewriter()
    .on('meta[property="og:title"]', new SetContent(title))
    .on('meta[property="og:description"]', new SetContent(desc))
    .on('meta[property="og:image"]', new SetContent(new URL(img, url).toString()))
    .on('meta[property="og:url"]', new SetContent(url.toString()))
    .transform(res);
}
