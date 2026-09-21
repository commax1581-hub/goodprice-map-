"""전체 업소에 카카오 장소ID 매칭
- 좌표 반경 검색(업소명) → 업소명 유사도 + 거리로 신뢰도 판정
- 중단 후 재실행 시 이어서 진행(resume)
결과: data/processed/kakao_match.csv
"""
import os, re, time, math, difflib
from concurrent.futures import ThreadPoolExecutor
import pandas as pd, requests

KEY = dict(l.strip().split('=', 1) for l in open('.env', encoding='utf-8') if '=' in l)['KAKAO_REST_KEY']
H = {'Authorization': 'KakaoAK ' + KEY}
URL = 'https://dapi.kakao.com/v2/local/search/keyword.json'
OUT = 'data/processed/kakao_match.csv'
DELAY = 0.02
WORKERS = 6
RADII = (100, 300)


def nname(s):
    s = re.sub(r'㈜|\(주\)|주식회사', '', str(s or ''))
    return re.sub(r'[\s\W_]+', '', s).lower()


def dist_m(la1, lo1, la2, lo2):
    R = 6371000
    p1, p2 = math.radians(la1), math.radians(la2)
    dp, dl = p2 - p1, math.radians(lo2 - lo1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def search(q, x, y, radius):
    for _ in range(4):
        try:
            r = requests.get(URL, headers=H, params={'query': q, 'x': x, 'y': y, 'radius': radius, 'size': 10,
                                                     'sort': 'distance'}, timeout=10)
        except requests.RequestException:
            time.sleep(1); continue
        if r.status_code == 200:
            return r.json()['documents']
        if r.status_code in (429, 500, 502, 503):
            time.sleep(2); continue
        return []
    return []


m = pd.read_csv('data/processed/goodprice_master.csv', dtype=str).fillna('')
done = set()
if os.path.exists(OUT):
    prev = pd.read_csv(OUT, dtype=str).fillna('')
    done = set(prev['관리번호'])
    rows = prev.to_dict('records')
    print('이어서 진행: 완료', len(done))
else:
    rows = []

todo = m[~m['관리번호'].isin(done)]
print('대상', len(todo))
t0 = time.time()
TOTAL = len(todo)
lock_rows = []


def handle(r):
    rec = {'관리번호': r['관리번호'], '업소명': r['업소명'], '주소': r['주소'], '업종': r['업종'],
           '카카오장소ID': '', '카카오장소명': '', '카카오카테고리': '', '카카오주소': '', '카카오링크': '',
           '거리m': '', '이름유사도': '', '신뢰도': '미매칭'}
    try:
        y, x = float(r['위도']), float(r['경도'])
    except ValueError:
        return rec
    key = nname(r['업소명'])
    best = None
    for radius in RADII:
        docs = search(r['업소명'], x, y, radius)
        time.sleep(DELAY)
        for d in docs:
            sim = difflib.SequenceMatcher(None, key, nname(d['place_name'])).ratio()
            dm = dist_m(y, x, float(d['y']), float(d['x']))
            if best is None or (sim, -dm) > (best[0], -best[1]):
                best = (sim, dm, d)
        if best and best[0] >= 0.9:
            break
    if best:
        sim, dm, d = best
        conf = 'HIGH' if sim >= 0.95 and dm <= 100 else 'MID' if sim >= 0.6 and dm <= 300 else 'LOW'
        if conf != 'LOW':
            rec.update({'카카오장소ID': d['id'], '카카오장소명': d['place_name'],
                        '카카오카테고리': d.get('category_name', ''),
                        '카카오주소': d.get('road_address_name') or d.get('address_name', ''),
                        '카카오링크': d['place_url'], '거리m': f'{dm:.0f}', '이름유사도': f'{sim:.2f}', '신뢰도': conf})
        else:
            rec.update({'카카오장소명': d['place_name'], '거리m': f'{dm:.0f}', '이름유사도': f'{sim:.2f}', '신뢰도': 'LOW'})
    return rec


with ThreadPoolExecutor(max_workers=WORKERS) as ex:
    for n, rec in enumerate(ex.map(handle, (r for _, r in todo.iterrows())), 1):
        rows.append(rec)
        if n % 300 == 0:
            pd.DataFrame(rows).to_csv(OUT, index=False, encoding='utf-8-sig')
            el = time.time() - t0
            print(f'{n}/{TOTAL} ({el/60:.1f}분, 남은 예상 {el/n*(TOTAL-n)/60:.0f}분)', flush=True)

df = pd.DataFrame(rows)
df.to_csv(OUT, index=False, encoding='utf-8-sig')
print('신뢰도', df.신뢰도.value_counts().to_dict())
