"""도로명주소 API로 전체 업소 주소 검증(주소 정제 단계)
- 수기 보정(data/address_overrides.csv)이 있으면 그 주소로 조회
- 원문 주소 조회 → 실패 시 도로명+건물번호만 추출해 재조회 (addr_util.lookup)
- 같은 주소 문구는 캐시(data/processed/address_cache.json)를 재사용 → 분기 갱신 때는 새·바뀐 주소만 API 호출
- 결과: data/processed/address_check.csv
  검증결과: 정상(원문) / 정상(정제후) / 주소없음 / 조회실패, 건물관리번호·층은 변경 분류(diff_update.py)에 쓰인다
"""
import time
from concurrent.futures import ThreadPoolExecutor
import pandas as pd
import addr_util as A

WORKERS = 4
OV = A.overrides()


def check(r):
    addr = OV.get(r['관리번호'], r['주소'])
    j = A.lookup(addr, r['시군구'])
    res = {'관리번호': r['관리번호'], '업소명': r['업소명'], '시도': r['시도'], '시군구': r['시군구'], '주소': r['주소'],
           **{k: v for k, v in j.items() if k != '조회'}, '층': A.floor_of(r['주소']),
           '수기보정': 'Y' if r['관리번호'] in OV else '', 'API조회': 'Y' if j['조회'] else ''}
    sgg = j.get('juso시군구', '')
    if r['시군구'] and sgg and r['시군구'] not in sgg and sgg not in r['시군구']:
        res['비고'] = f"시군구 불일치(원천 {r['시군구']} / 주소DB {sgg})"
    return res


if __name__ == '__main__':
    m = pd.read_csv('data/processed/goodprice_master.csv', dtype=str).fillna('')
    print('대상', len(m), '· 수기 보정', len(OV))
    t0 = time.time(); rows = []
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        for n, rec in enumerate(ex.map(check, (r for _, r in m.iterrows())), 1):
            rows.append(rec)
            if n % 1000 == 0:
                A.save_cache()
                el = time.time() - t0
                print(f'{n}/{len(m)} ({el/60:.1f}분)', flush=True)
    A.save_cache()
    df = pd.DataFrame(rows)
    df.to_csv('data/processed/address_check.csv', index=False, encoding='utf-8-sig')
    print('결과', df.검증결과.value_counts().to_dict(), '· API 호출', (df.API조회 == 'Y').sum(), '· 건물관리번호 확보', (df.건물관리번호 != '').sum())
