"""검수대상 상가(상권)정보 교차검증 — 국세청/카드사 기반 사업장 존재 확인
좌표 반경 100m → 300m 조회 후 상호명 대조
결과: data/processed/sbiz_verify.csv
"""
import re, time, math, difflib
from concurrent.futures import ThreadPoolExecutor
import pandas as pd, requests

KEY = dict(l.strip().split('=', 1) for l in open('.env', encoding='utf-8') if '=' in l)['DATAGOKR_KEY']
URL = 'https://apis.data.go.kr/B553077/api/open/sdsc2/storeListInRadius'
WORKERS = 5
RADII = (100, 300)


def nname(s):
    s = re.sub(r'㈜|\(주\)|주식회사', '', str(s or ''))
    return re.sub(r'[\s\W_]+', '', s).lower()


def dist_m(la1, lo1, la2, lo2):
    R = 6371000
    p1, p2 = math.radians(la1), math.radians(la2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lo2 - lo1) / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def fetch(cx, cy, radius):
    for _ in range(3):
        try:
            r = requests.get(URL, params={'serviceKey': KEY, 'radius': radius, 'cx': cx, 'cy': cy,
                                          'numOfRows': 100, 'pageNo': 1, 'type': 'json'}, timeout=20)
        except requests.RequestException:
            time.sleep(1); continue
        if r.status_code != 200:
            time.sleep(1); continue
        try:
            body = r.json().get('body') or {}
            return body.get('items') or []
        except ValueError:
            return []
    return []


def verify(r):
    res = {'관리번호': r['관리번호'], '업소명': r['업소명'], '주소': r['주소'], '업종': r['업종'],
           '기존판정': r['네이버판정'], '상가업소번호': '', '상가상호': '', '상가업종': '', '상가주소': '',
           '상가층호': '', '거리m': '', '유사도': '', '상가판정': '없음'}
    try:
        cy, cx = float(r['위도']), float(r['경도'])
    except ValueError:
        res['상가판정'] = '좌표없음'; return res
    key = nname(r['업소명'])
    best = None
    for radius in RADII:
        for it in fetch(cx, cy, radius):
            try:
                ln, lt = float(it['lon']), float(it['lat'])
            except (KeyError, TypeError, ValueError):
                continue
            nm = it.get('bizesNm') or ''
            sim = difflib.SequenceMatcher(None, key, nname(nm)).ratio()
            dm = dist_m(cy, cx, lt, ln)
            if best is None or sim > best[0] or (sim == best[0] and dm < best[1]):
                best = (sim, dm, it)
        if best and best[0] >= 0.9:
            break
    if best:
        sim, dm, it = best
        if sim >= 0.6:
            res.update({'상가업소번호': it.get('bizesId', ''), '상가상호': it.get('bizesNm', ''),
                        '상가업종': it.get('indsSclsNm', ''), '상가주소': it.get('rdnmAdr', ''),
                        '상가층호': f"{it.get('flrNo','')}층 {it.get('hoNo','')}".strip(),
                        '거리m': f'{dm:.0f}', '유사도': f'{sim:.2f}',
                        '상가판정': '확인됨' if sim >= 0.8 else '유사확인'})
        else:
            res.update({'상가상호': it.get('bizesNm', ''), '거리m': f'{dm:.0f}', '유사도': f'{sim:.2f}',
                        '상가판정': '반경내 미일치'})
    return res


d = pd.read_csv('data/processed/goodprice_final.csv', dtype=str).fillna('')
target = d[d.데이터등급 == '검수필요']
print('대상', len(target))
t0 = time.time(); rows = []
with ThreadPoolExecutor(max_workers=WORKERS) as ex:
    for n, rec in enumerate(ex.map(verify, (r for _, r in target.iterrows())), 1):
        rows.append(rec)
        if n % 150 == 0:
            print(f'{n}/{len(target)} ({(time.time()-t0)/60:.1f}분)', flush=True)

sv = pd.DataFrame(rows)
sv.to_csv('data/processed/sbiz_verify.csv', index=False, encoding='utf-8-sig')
print(sv.상가판정.value_counts().to_dict())
print(pd.crosstab(sv.기존판정, sv.상가판정).to_string())
