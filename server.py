"""착한가격 지도 — 정적 서버 + AI 질의해석 중계(/api/parse)
키는 .env에서만 읽고 브라우저로 내보내지 않는다.
폴백 순서: 제미나이(무료 한도) → 클로드(선택, 키 있을 때만)
실행: python server.py [포트]
"""
import json, os, re, sys, time, hashlib, io, threading, html as htmllib, urllib.request, urllib.error, urllib.parse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).parent
ENV = dict(l.strip().split('=', 1) for l in open(ROOT / '.env', encoding='utf-8') if '=' in l)
GEMINI_KEY = ENV.get('GEMINI_KEY', '')
CLAUDE_KEY = ENV.get('ANTHROPIC_API_KEY', '')
GEMINI_MODEL = 'gemini-3.1-flash-lite'
CLAUDE_MODEL = 'claude-haiku-4-5'

SYSTEM = '''한국 착한가격업소 검색 앱의 질의 해석기다. 사용자 문장을 검색 조건 JSON으로만 변환하라.
- upjong은 다음 중 하나: 한식,중식,일식,양식,베이커리,기타요식업,미용업,이용업,세탁업,목욕업,숙박업,기타비요식업
- keyword는 구체적 메뉴명(예: 김밥,칼국수,커트). 없으면 빈 문자열
- facilities는 다음에서만 고른다: 주차,포장,배달,예약,단체가능,와이파이,반려동물,유아시설,장애인시설,임산부우대,지역화폐,남녀화장실
- sido/sgg는 한국 행정구역 정식 명칭(예: 부산광역시, 해운대구)
- 해당 없으면 빈 문자열 / 0 / false'''

SCHEMA = {'type': 'object', 'properties': {
    'sido': {'type': 'string'}, 'sgg': {'type': 'string'}, 'upjong': {'type': 'string'},
    'keyword': {'type': 'string'}, 'maxPrice': {'type': 'integer'},
    'facilities': {'type': 'array', 'items': {'type': 'string'}},
    'openNow': {'type': 'boolean'}, 'near': {'type': 'boolean'}}}


def post_json(url, payload, headers, timeout=20):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                 headers={'Content-Type': 'application/json', **headers})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def ask_gemini(text, retry=True):
    url = f'https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_KEY}'
    body = {'systemInstruction': {'parts': [{'text': SYSTEM}]},
            'contents': [{'parts': [{'text': text}]}],
            'generationConfig': {'responseMimeType': 'application/json', 'responseSchema': SCHEMA, 'temperature': 0}}
    try:
        j = post_json(url, body, {})
    except urllib.error.HTTPError as e:              # 일시 오류(과부하·한도) → 한 번 재시도
        if retry and e.code in (429, 500, 503):
            time.sleep(0.8); return ask_gemini(text, retry=False)
        raise
    return json.loads(j['candidates'][0]['content']['parts'][0]['text'])


def ask_claude(text):
    body = {'model': CLAUDE_MODEL, 'max_tokens': 512,
            'system': SYSTEM + '\nJSON 객체만 출력하라. 설명 금지.',
            'messages': [{'role': 'user', 'content': text}]}
    j = post_json('https://api.anthropic.com/v1/messages', body,
                  {'x-api-key': CLAUDE_KEY, 'anthropic-version': '2023-06-01'})
    out = ''.join(b.get('text', '') for b in j.get('content', []) if b.get('type') == 'text')
    return json.loads(out[out.find('{'): out.rfind('}') + 1])


NOTICE_URL = 'https://www.goodprice.go.kr/cmnt/boardList.do?bbsId=BBSCTT_00101'
NOTICE_CACHE = ROOT / 'data' / 'notices.json'
NOTICE_TTL = 24 * 3600          # 하루 1회만 공식 누리집에 요청


def fetch_notices():
    """공지사항 목록에서 제목·날짜만 수집(본문·이미지·이용후기는 수집하지 않음)"""
    req = urllib.request.Request(NOTICE_URL, headers={'User-Agent': 'Mozilla/5.0 (personal-study; goodprice map mashup)'})
    with urllib.request.urlopen(req, timeout=15) as r:
        page = r.read().decode('utf-8', 'replace')
    items = []
    for row in re.findall(r'<tr>(.*?)</tr>', page, re.S):
        m = re.search(r"goInfo\('(\d+)'\);\">\s*(.*?)\s*</a>.*?<td>[^<]*</td>\s*<td>(\d{4}-\d{2}-\d{2})</td>", row, re.S)
        if not m:
            continue
        items.append({'id': m.group(1), 'title': htmllib.unescape(re.sub(r'\s+', ' ', m.group(2))).strip(),
                      'date': m.group(3), 'pinned': 'notice_display' in row})
    items.sort(key=lambda x: (not x['pinned'], x['date']), reverse=False)
    pinned = sorted([i for i in items if i['pinned']], key=lambda x: x['date'], reverse=True)
    rest = sorted([i for i in items if not i['pinned']], key=lambda x: x['date'], reverse=True)
    return (pinned + rest)[:6]


def get_notices():
    cached = None
    if NOTICE_CACHE.exists():
        cached = json.loads(NOTICE_CACHE.read_text(encoding='utf-8'))
        if time.time() - cached.get('fetched_at', 0) < NOTICE_TTL:
            return cached
    try:
        data = {'fetched_at': time.time(), 'source': NOTICE_URL, 'items': fetch_notices()}
        NOTICE_CACHE.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding='utf-8')
        return data
    except Exception as e:                       # 수집 실패 시 이전 결과 유지
        return cached or {'fetched_at': 0, 'source': NOTICE_URL, 'items': [], 'error': type(e).__name__}


THUMB_DIR = ROOT / 'data' / 'thumbs'
THUMB_PREFIX = 'https://www.goodprice.go.kr/comm/showImageFile.do?'   # 공식 사진 주소만 허용
THUMB_W = 360                    # 목록(72px)·홈 카드(208px) 고해상도 화면까지 충분
THUMB_FAIL_TTL = 24 * 3600       # 실패한 사진은 하루 동안 다시 요청하지 않음
THUMB_SEM = threading.Semaphore(4)   # 공식 서버 동시 요청 제한


def make_thumb(url):
    """공식 사진을 받아 작게 줄여 저장(목록용 사본). 상세 화면은 원본 링크를 그대로 쓴다."""
    from PIL import Image, ImageOps
    THUMB_DIR.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha1(url.encode()).hexdigest()
    out, fail = THUMB_DIR / f'{key}.webp', THUMB_DIR / f'{key}.fail'
    if out.exists():
        return out.read_bytes()
    if fail.exists() and time.time() - fail.stat().st_mtime < THUMB_FAIL_TTL:
        return None
    try:
        with THUMB_SEM:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (personal-study; goodprice map mashup)'})
            with urllib.request.urlopen(req, timeout=20) as r:
                raw = r.read(15 * 1024 * 1024)
        im = ImageOps.exif_transpose(Image.open(io.BytesIO(raw))).convert('RGB')
        im.thumbnail((THUMB_W, THUMB_W * 2))
        buf = io.BytesIO(); im.save(buf, 'WEBP', quality=72)
        out.write_bytes(buf.getvalue())
        return buf.getvalue()
    except Exception:
        fail.write_text('')
        return None


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(ROOT / 'app'), **kw)

    extensions_map = {**SimpleHTTPRequestHandler.extensions_map, '.webmanifest': 'application/manifest+json',
                      '.webp': 'image/webp'}

    def end_headers(self):                      # 개발 중 캐시 방지
        if self.path.endswith(('.js', '.css', '.html')) or self.path == '/':
            self.send_header('Cache-Control', 'no-store, must-revalidate')
        super().end_headers()

    def log_message(self, fmt, *args):
        if '/api/' in (args[0] if args else ''):
            super().log_message(fmt, *args)

    def _send(self, code, obj):
        raw = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        path = urllib.parse.urlsplit(self.path).path
        if path in ('/', '/index.html'):
            return self._send_index()
        if self.path == '/api/notices':
            return self._send(200, get_notices())
        if self.path == '/api/status':
            return self._send(200, {'gemini': bool(GEMINI_KEY), 'claude': bool(CLAUDE_KEY)})
        if self.path.startswith('/api/thumb?'):
            u = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query).get('u', [''])[0]
            if not u.startswith(THUMB_PREFIX):
                return self._send(400, {'error': 'bad url'})
            data = make_thumb(u)
            if data is None:
                return self._send(404, {'error': 'no image'})
            self.send_response(200)
            self.send_header('Content-Type', 'image/webp')
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'public, max-age=2592000')
            self.end_headers()
            return self.wfile.write(data)
        return super().do_GET()

    def _send_index(self):
        """공유 링크(?s=&id=)로 들어오면 카카오톡 등 미리보기에 업소 이름·가격·사진이 나오도록 OG 태그를 채운다."""
        page = (ROOT / 'app' / 'index.html').read_text(encoding='utf-8')
        host = self.headers.get('X-Forwarded-Host') or self.headers.get('Host') or 'localhost'
        proto = self.headers.get('X-Forwarded-Proto') or 'http'
        base = f'{proto}://{host}'
        qs = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
        title, desc, img = '착한가격 지도', '전국 착한가격업소 13,000여 곳을 지도에서 찾아보세요.', f'{base}/assets/og-default.png'
        sido, sid = qs.get('s', [''])[0], qs.get('id', [''])[0]
        if re.fullmatch(r'\d{2}', sido) and re.fullmatch(r'GP\d+', sid):
            f = ROOT / 'app' / 'data' / f'{sido}.json'
            it = next((i for i in json.loads(f.read_text(encoding='utf-8')) if i['i'] == sid), None) if f.exists() else None
            if it:
                m = it['m'][0] if it.get('m') else None
                title = f"{it['n']} · 착한가격업소"
                desc = ' · '.join(x for x in [f"{m[0]} {m[1]:,}원" if m and m[1] is not None else '', it.get('a', '')] if x)
                if it.get('img') and (ROOT / 'app' / 'thumbs' / f"{it['i']}.webp").exists():
                    img = f"{base}/thumbs/{it['i']}.webp"
        e = lambda s: htmllib.escape(s, quote=True)
        og = (f'<meta property="og:type" content="website">\n<meta property="og:site_name" content="착한가격 지도">\n'
              f'<meta property="og:title" content="{e(title)}">\n<meta property="og:description" content="{e(desc)}">\n'
              f'<meta property="og:image" content="{e(img)}">\n<meta property="og:url" content="{e(base + self.path)}">\n'
              f'<meta name="twitter:card" content="summary_large_image">')
        page = re.sub(r'<!--OG-->.*?<!--/OG-->', lambda _: og, page, flags=re.S)
        raw = page.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_POST(self):
        if self.path != '/api/parse':
            return self._send(404, {'error': 'not found'})
        n = int(self.headers.get('Content-Length', 0))
        try:
            text = json.loads(self.rfile.read(n)).get('text', '').strip()[:200]
        except Exception:
            return self._send(400, {'error': 'bad request'})
        if not text:
            return self._send(400, {'error': 'empty'})

        errors = []
        for name, fn, ok in (('gemini', ask_gemini, GEMINI_KEY), ('claude', ask_claude, CLAUDE_KEY)):
            if not ok:
                errors.append(f'{name}: 키 없음'); continue
            try:
                return self._send(200, {'source': name, 'parsed': fn(text)})
            except urllib.error.HTTPError as e:
                errors.append(f'{name}: HTTP {e.code}')
            except Exception as e:
                errors.append(f'{name}: {type(e).__name__}')
        return self._send(502, {'error': 'AI 해석 실패', 'detail': errors})


if __name__ == '__main__':
    port = int(next((a for a in sys.argv[1:] if a.isdigit()), 8000))
    host = '0.0.0.0' if '--lan' in sys.argv else '127.0.0.1'      # --lan: 같은 와이파이의 휴대폰에서 접속 테스트
    print(f'착한가격 지도  http://localhost:{port}')
    print(f'  제미나이 {"O" if GEMINI_KEY else "X"} / 클로드 {"O" if CLAUDE_KEY else "X"}')
    if host == '0.0.0.0':
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.connect(('8.8.8.8', 80))
        print(f'  휴대폰(같은 와이파이): http://{s.getsockname()[0]}:{port}'); s.close()
    ThreadingHTTPServer((host, port), Handler).serve_forever()
