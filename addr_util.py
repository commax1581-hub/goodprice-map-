"""주소 정제 공용 모듈 — 표기 정리, 도로명주소 API 대조(캐시), 건물관리번호·층 추출, 수기 보정
- 같은 주소 문구는 한 번만 조회하고 data/processed/address_cache.json에 저장해 다음 분기에 재사용한다.
- 수기 보정: data/address_overrides.csv (관리번호, 수정주소, 사유, 날짜) — 다음 분기에도 유지
- 비교·식별에는 건물관리번호(도로명주소 DB의 건물 고유번호)를 쓴다. 표기만 다른 주소가 '이전'으로 잡히지 않게.
설계: docs/공공데이터-파이프라인.md 6장(좌표)·8장(분기 갱신), 주소 정제 단계
"""
import json, re, threading, time
from pathlib import Path
import requests

ROOT = Path(__file__).parent
CACHE_PATH = ROOT / 'data' / 'processed' / 'address_cache.json'
OVERRIDES = ROOT / 'data' / 'address_overrides.csv'
URL = 'https://business.juso.go.kr/addrlink/addrLinkApi.do'
ROAD_RE = re.compile(r'([가-힣A-Za-z0-9·.]+?(?:로|길))\s*(?:(\d+)\s*(번?길))?\s*(?:지하\s*)?(\d+(?:-\d+)?)')
FLOOR_RE = re.compile(r'(지하\s*\d+\s*층|\d+\s*층|B\s*\d+\s*층?)')

_lock = threading.Lock()
_cache = None
_key = None


def clean(a):
    """괄호·쉼표 뒤·층 이하 제거, 공백 정리"""
    a = re.sub(r'\([^)]*\)', ' ', str(a or ''))
    a = re.sub(r',.*$', '', a)
    a = re.sub(r'\s*(지하\s*)?\d+층.*$', '', a)
    return re.sub(r'\s+', ' ', a).strip()


def road_only(a):
    """도로명 + 건물번호만 (예: '토성로 92')"""
    m = ROAD_RE.search(clean(a))
    if not m:
        return ''
    num = (m.group(2) + m.group(3) + ' ') if m.group(2) else ''
    return f'{m.group(1)} {num}{m.group(4)}'.replace('  ', ' ')


def road_key(a):
    """비교용 도로명+건물번호 키(공백 없음). 건물관리번호를 못 얻었을 때 대신 쓴다"""
    return re.sub(r'\s+', '', road_only(a))


def floor_of(a):
    m = FLOOR_RE.search(str(a or ''))
    return re.sub(r'\s+', '', m.group(1)) if m else ''


def overrides():
    """관리번호 → 수정주소 (사람이 확인해 고친 주소)"""
    if not OVERRIDES.exists():
        return {}
    import csv
    with open(OVERRIDES, encoding='utf-8-sig') as f:
        return {r['관리번호']: r['수정주소'] for r in csv.DictReader(f) if r.get('관리번호') and r.get('수정주소')}


def _load():
    global _cache, _key
    if _cache is None:
        _cache = json.loads(CACHE_PATH.read_text(encoding='utf-8')) if CACHE_PATH.exists() else {}
    if _key is None:
        env = dict(l.strip().split('=', 1) for l in open(ROOT / '.env', encoding='utf-8') if '=' in l)
        _key = env['JUSO_KEY']


def save_cache():
    if _cache is not None:
        with _lock:
            CACHE_PATH.write_text(json.dumps(_cache, ensure_ascii=False), encoding='utf-8')


def _query(kw):
    err = ''
    for _ in range(3):
        try:
            r = requests.get(URL, params={'confmKey': _key, 'currentPage': 1, 'countPerPage': 5,
                                          'keyword': kw, 'resultType': 'json'}, timeout=10)
            j = r.json()['results']
            if j['common']['errorCode'] != '0':
                return None, j['common']['errorMessage']
            return j['juso'], ''
        except Exception as e:
            time.sleep(1); err = str(e)[:40]
    return None, err


def lookup(addr, sgg=''):
    """주소 → {검증결과, 정규주소, 우편번호, juso시도, juso시군구, 행정동, 건물명, 건물관리번호, 비고}
    캐시에 있으면 API를 부르지 않는다. 결과 dict에 '조회'(True=이번에 API 호출)를 붙인다."""
    _load()
    key = clean(addr)
    with _lock:
        hit = _cache.get(key)
    if hit is not None:
        return {**hit, '조회': False}
    juso, err = _query(key) if key else (None, '')
    how = '정상(원문)'
    if not juso:
        ro = road_only(addr)
        if ro:
            juso, err = _query(f'{sgg} {ro}'.strip())
            how = '정상(정제후)'
    if juso:
        j = juso[0]
        res = {'검증결과': how, '정규주소': j.get('roadAddr', ''), '우편번호': j.get('zipNo', ''),
               'juso시도': j.get('siNm', ''), 'juso시군구': j.get('sggNm', ''), '행정동': j.get('emdNm', ''),
               '건물명': j.get('bdNm', ''), '건물관리번호': j.get('bdMgtSn', ''), '비고': ''}
    else:
        res = {'검증결과': '조회실패' if err else '주소없음', '정규주소': '', '우편번호': '', 'juso시도': '',
               'juso시군구': '', '행정동': '', '건물명': '', '건물관리번호': '', '비고': err}
    if res['검증결과'] != '조회실패':          # 일시 오류는 저장하지 않고 다음에 다시 조회
        with _lock:
            _cache[key] = res
    return {**res, '조회': True}
