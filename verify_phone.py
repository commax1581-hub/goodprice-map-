"""검수대상 전화번호 기반 재검증
1) 카카오 전화번호 검색 → 같은 전화면 동일 업소로 확정(이름·거리 무관)
2) 실패 시 좌표 반경 500m 업소명 검색 후보들의 전화번호 비교
결과: data/processed/phone_verify.csv
"""
import re, time, math
from concurrent.futures import ThreadPoolExecutor
import pandas as pd, requests

KEY = dict(l.strip().split('=', 1) for l in open('.env', encoding='utf-8') if '=' in l)['KAKAO_REST_KEY']
H = {'Authorization': 'KakaoAK ' + KEY}
URL = 'https://dapi.kakao.com/v2/local/search/keyword.json'
WORKERS = 6


def digits(s):
    return re.sub(r'\D', '', str(s or ''))


def dist_m(la1, lo1, la2, lo2):
    R = 6371000
    p1, p2 = math.radians(la1), math.radians(la2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lo2 - lo1) / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def search(q, **extra):
    for _ in range(3):
        try:
            r = requests.get(URL, headers=H, params={'query': q, 'size': 10, **extra}, timeout=10)
        except requests.RequestException:
            time.sleep(1); continue
        if r.status_code == 200:
            return r.json()['documents']
        if r.status_code in (429, 500, 502, 503):
            time.sleep(2); continue
        return []
    return []


def verify(r):
    res = {'관리번호': r['관리번호'], '업소명': r['업소명'], '주소': r['주소'], '전화번호': r['전화번호'],
           '기존판정': r['네이버판정'], '전화매칭': '', '카카오장소ID': '', '카카오장소명': '',
           '카카오링크': '', '카카오전화': '', '거리m': ''}
    tel = digits(r['전화번호'])
    if len(tel) < 8:
        res['전화매칭'] = '전화번호없음'; return res
    try:
        y, x = float(r['위도']), float(r['경도'])
    except ValueError:
        y = x = None
    hit = None
    for d in search(r['전화번호']):          # 1) 전화번호 직접 검색
        if digits(d.get('phone')) == tel:
            hit = ('전화일치(직접검색)', d); break
    if not hit and y:                        # 2) 반경 500m 업소명 검색 후보의 전화 비교
        for d in search(r['업소명'], x=x, y=y, radius=500):
            if digits(d.get('phone')) == tel:
                hit = ('전화일치(반경검색)', d); break
    if hit:
        how, d = hit
        dm = dist_m(y, x, float(d['y']), float(d['x'])) if y else None
        res.update({'전화매칭': how, '카카오장소ID': d['id'], '카카오장소명': d['place_name'],
                    '카카오링크': d['place_url'], '카카오전화': d.get('phone', ''),
                    '거리m': f'{dm:.0f}' if dm is not None else ''})
    else:
        res['전화매칭'] = '불일치'
    return res


d = pd.read_csv('data/processed/match_status.csv', dtype=str).fillna('')
target = d[d.최종상태 == '검수필요']
print('대상', len(target))
t0 = time.time(); rows = []
with ThreadPoolExecutor(max_workers=WORKERS) as ex:
    for n, rec in enumerate(ex.map(verify, (r for _, r in target.iterrows())), 1):
        rows.append(rec)
        if n % 200 == 0:
            el = time.time() - t0
            print(f'{n}/{len(target)} ({el/60:.1f}분)', flush=True)

pv = pd.DataFrame(rows)
pv.to_csv('data/processed/phone_verify.csv', index=False, encoding='utf-8-sig')
print(pv.전화매칭.value_counts().to_dict())
print(pd.crosstab(pv.기존판정, pv.전화매칭).to_string())
