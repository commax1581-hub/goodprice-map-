"""카카오 매칭 등급 확정 + 네이버 지역검색 교차검증
- 중복 카카오ID 정리(이름 유사도 높은 쪽 유지)
- 자동채택: HIGH / MID·LOW 30m 이내
- 검증대상: MID·LOW 30m 초과, 미매칭, 중복 해제분 → 네이버 지역검색
결과: data/processed/naver_verify.csv, match_status.csv
"""
import re, time, math, difflib, html
from concurrent.futures import ThreadPoolExecutor
import pandas as pd, requests

E = dict(l.strip().split('=', 1) for l in open('.env', encoding='utf-8') if '=' in l)
H = {'X-NCP-APIGW-API-KEY-ID': E['NAVER_CLIENT_ID'], 'X-NCP-APIGW-API-KEY': E['NAVER_CLIENT_SECRET']}
URL = 'https://naverapihub.apigw.ntruss.com/search/v1/local'
NEAR_M = 30      # 자동채택 거리 기준
CONFIRM_M = 100  # 네이버 확인 거리 기준
WORKERS = 5


def nname(s):
    s = re.sub(r'㈜|\(주\)|주식회사', '', str(s or ''))
    return re.sub(r'[\s\W_]+', '', s).lower()


def dist_m(la1, lo1, la2, lo2):
    R = 6371000
    p1, p2 = math.radians(la1), math.radians(la2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lo2 - lo1) / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


m = pd.read_csv('data/processed/goodprice_master.csv', dtype=str).fillna('')
k = pd.read_csv('data/processed/kakao_match.csv', dtype=str).fillna('')
d = m.merge(k[['관리번호', '카카오장소ID', '카카오장소명', '카카오카테고리', '카카오주소', '카카오링크', '거리m', '이름유사도', '신뢰도']], on='관리번호')

# ---- 1) 중복 카카오ID 정리 ----
dup_released = []
for pid, g in d[d.카카오장소ID != ''].groupby('카카오장소ID'):
    if len(g) < 2:
        continue
    keep = g.이름유사도.astype(float).idxmax()
    for i in g.index:
        if i != keep:
            dup_released.append(d.at[i, '관리번호'])
            d.loc[i, ['카카오장소ID', '카카오장소명', '카카오링크', '거리m', '이름유사도']] = ''
            d.loc[i, '신뢰도'] = '중복해제'
print('중복 해제', len(dup_released))

# ---- 2) 등급 확정 ----
def decide(r):
    if r.신뢰도 == 'HIGH':
        return '자동채택'
    if r.신뢰도 in ('MID', 'LOW'):
        return '자동채택' if float(r.거리m or 9999) <= NEAR_M else '네이버검증'
    return '네이버검증'  # 미매칭, 중복해제


d['매칭상태'] = d.apply(decide, axis=1)
print(d.매칭상태.value_counts().to_dict())
target = d[d.매칭상태 == '네이버검증']
print('네이버 검증 대상', len(target))


def verify(r):
    res = {'관리번호': r['관리번호'], '업소명': r['업소명'], '주소': r['주소'], '업종': r['업종'],
           '카카오신뢰도': r['신뢰도'], '카카오장소명': r['카카오장소명'], '카카오거리m': r['거리m'],
           '네이버명': '', '네이버주소': '', '네이버카테고리': '', '네이버거리m': '', '네이버판정': '없음'}
    try:
        y, x = float(r['위도']), float(r['경도'])
    except ValueError:
        res['네이버판정'] = '좌표없음'; return res
    key = nname(r['업소명'])
    best = None
    for q in (f"{r['시군구']} {r['업소명']}", r['업소명']):
        try:
            rp = requests.get(URL, headers=H, params={'query': q, 'display': 5}, timeout=10)
        except requests.RequestException:
            time.sleep(1); continue
        if rp.status_code != 200:
            if rp.status_code == 429:
                time.sleep(2)
            continue
        for it in rp.json().get('items', []):
            nm = html.unescape(re.sub('<[^>]+>', '', it['title']))
            try:
                nx, ny = int(it['mapx']) / 1e7, int(it['mapy']) / 1e7
            except (ValueError, KeyError):
                continue
            dm = dist_m(y, x, ny, nx)
            sim = difflib.SequenceMatcher(None, key, nname(nm)).ratio()
            if best is None or (sim >= 0.6) > (best[0] >= 0.6) or (sim >= 0.6 and dm < best[1]) or (best[0] < 0.6 and sim > best[0]):
                best = (sim, dm, nm, it.get('roadAddress', ''), it.get('category', ''))
        if best and best[0] >= 0.6 and best[1] <= CONFIRM_M:
            break
        time.sleep(0.05)
    if best:
        sim, dm, nm, addr, cat = best
        res.update({'네이버명': nm, '네이버주소': addr, '네이버카테고리': cat, '네이버거리m': f'{dm:.0f}'})
        if sim >= 0.6 and dm <= CONFIRM_M:
            res['네이버판정'] = '확인됨'
        elif dm <= CONFIRM_M:
            res['네이버판정'] = '상호상이'
        else:
            res['네이버판정'] = '위치상이'
    return res


t0 = time.time()
rows = []
with ThreadPoolExecutor(max_workers=WORKERS) as ex:
    for n, rec in enumerate(ex.map(verify, (r for _, r in target.iterrows())), 1):
        rows.append(rec)
        if n % 300 == 0:
            el = time.time() - t0
            print(f'{n}/{len(target)} ({el/60:.1f}분, 남은 {el/n*(len(target)-n)/60:.0f}분)', flush=True)

nv = pd.DataFrame(rows)
nv.to_csv('data/processed/naver_verify.csv', index=False, encoding='utf-8-sig')
print('네이버 판정', nv.네이버판정.value_counts().to_dict())

# ---- 3) 최종 상태 ----
jm = dict(zip(nv.관리번호, nv.네이버판정))
d['네이버판정'] = d.관리번호.map(jm).fillna('')
d['네이버명'] = d.관리번호.map(dict(zip(nv.관리번호, nv.네이버명))).fillna('')
d['최종상태'] = d.apply(lambda r: '자동채택' if r.매칭상태 == '자동채택'
                    else ('네이버확인' if r.네이버판정 == '확인됨' else '검수필요'), axis=1)
d.to_csv('data/processed/match_status.csv', index=False, encoding='utf-8-sig')
print('최종', d.최종상태.value_counts().to_dict())
