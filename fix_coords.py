"""좌표 미확보 업소 카카오 보정
1) 주소검색(도로명/지번) → 2) 실패 시 키워드검색(업소명+시군구, 시군구 범위 확인)
결과: data/processed/coord_overrides.csv (검수용), goodprice_master_fixed.csv
"""
import os, re, time, json
import pandas as pd, requests

KEY = dict(l.strip().split('=', 1) for l in open('.env', encoding='utf-8') if '=' in l)['KAKAO_REST_KEY']
H = {'Authorization': 'KakaoAK ' + KEY}
BASE = 'https://dapi.kakao.com/v2/local/search/'
DELAY = 0.15

m = pd.read_csv('data/processed/goodprice_master.csv', dtype=str).fillna('')
target = m[m['좌표출처'] == '미확보'].copy()
print('보정 대상', len(target))


def get(url, params):
    for _ in range(3):
        r = requests.get(BASE + url, headers=H, params=params, timeout=10)
        if r.status_code == 200:
            return r.json()['documents']
        if r.status_code == 429:
            time.sleep(2); continue
        return []
    return []


def clean_addr(a):
    a = re.sub(r'\([^)]*\)', ' ', a)
    a = re.sub(r',.*$', '', a)
    a = re.sub(r'\s*(지하)?\s*\d+층.*$', '', a)
    return re.sub(r'\s+', ' ', a).strip()


rows = []
for n, (_, r) in enumerate(target.iterrows(), 1):
    res = {'관리번호': r['관리번호'], '업소명': r['업소명'], '주소': r['주소'], '시도': r['시도'], '시군구': r['시군구'],
           '위도': '', '경도': '', '좌표출처': '', '카카오장소ID': '', '카카오장소명': '', '카카오주소': '', '검수필요': 'Y', '비고': ''}
    docs = get('address.json', {'query': clean_addr(r['주소']), 'size': 3})
    time.sleep(DELAY)
    if docs:
        d = docs[0]
        res.update(위도=d['y'], 경도=d['x'], 좌표출처='kakao_addr', 카카오주소=d['address_name'], 검수필요='N')
    else:  # 주소 실패 → 업소명 검색
        docs = get('keyword.json', {'query': f"{r['시군구']} {r['업소명']}", 'size': 5})
        time.sleep(DELAY)
        hit = next((d for d in docs if r['시군구'] and r['시군구'] in (d.get('road_address_name') or d.get('address_name') or '')), None)
        if hit:
            res.update(위도=hit['y'], 경도=hit['x'], 좌표출처='kakao_place', 카카오장소ID=hit['id'],
                       카카오장소명=hit['place_name'], 카카오주소=hit.get('road_address_name') or hit.get('address_name'),
                       검수필요='Y', 비고='업소명 검색 결과 → 업소명 일치 여부 확인 필요')
        else:
            res['비고'] = '주소·업소명 모두 검색 실패 → 수동 확인'
    rows.append(res)
    if n % 50 == 0:
        print(n, flush=True)

ov = pd.DataFrame(rows)
ov.to_csv('data/processed/coord_overrides.csv', index=False, encoding='utf-8-sig')
print(ov.좌표출처.replace('', '실패').value_counts().to_dict())

idx = m.set_index('관리번호')
for _, r in ov[ov.위도 != ''].iterrows():
    idx.loc[r['관리번호'], ['위도', '경도', '좌표출처']] = [r['위도'], r['경도'], r['좌표출처']]
idx.reset_index().to_csv('data/processed/goodprice_master.csv', index=False, encoding='utf-8-sig')
print('좌표 현황', idx.좌표출처.value_counts().to_dict())
