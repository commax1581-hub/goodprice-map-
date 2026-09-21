"""도로명주소 API로 전체 업소 주소 검증
- 원문 주소 조회 → 실패 시 도로명+건물번호만 추출해 재조회
- 결과: data/processed/address_check.csv
  검증결과: 정상(원문) / 정상(정제후) / 주소없음 / 조회실패
"""
import re, time
from concurrent.futures import ThreadPoolExecutor
import pandas as pd, requests

KEY = dict(l.strip().split('=', 1) for l in open('.env', encoding='utf-8') if '=' in l)['JUSO_KEY']
URL = 'https://business.juso.go.kr/addrlink/addrLinkApi.do'
WORKERS = 4
ROAD_RE = re.compile(r'([가-힣A-Za-z0-9·.]+?(?:로|길))\s*(?:(\d+)\s*(번?길))?\s*(?:지하\s*)?(\d+(?:-\d+)?)')


def clean(a):
    a = re.sub(r'\([^)]*\)', ' ', str(a))
    a = re.sub(r',.*$', '', a)
    a = re.sub(r'\s*(지하\s*)?\d+층.*$', '', a)
    return re.sub(r'\s+', ' ', a).strip()


def road_only(a):
    m = ROAD_RE.search(clean(a))
    if not m:
        return ''
    num = (m.group(2) + m.group(3) + ' ') if m.group(2) else ''
    return f'{m.group(1)} {num}{m.group(4)}'.replace('  ', ' ')


def query(kw):
    for _ in range(3):
        try:
            r = requests.get(URL, params={'confmKey': KEY, 'currentPage': 1, 'countPerPage': 5,
                                          'keyword': kw, 'resultType': 'json'}, timeout=10)
            j = r.json()['results']
            if j['common']['errorCode'] != '0':
                return None, j['common']['errorMessage']
            return j['juso'], ''
        except Exception as e:
            time.sleep(1); err = str(e)[:40]
    return None, err


def check(r):
    res = {'관리번호': r['관리번호'], '업소명': r['업소명'], '시도': r['시도'], '시군구': r['시군구'], '주소': r['주소'],
           '검증결과': '', '정규주소': '', '우편번호': '', 'juso시도': '', 'juso시군구': '', '행정동': '', '건물명': '', '비고': ''}
    juso, err = query(clean(r['주소']))
    how = '정상(원문)'
    if not juso:
        ro = road_only(r['주소'])
        if ro:
            juso, err = query(f"{r['시군구']} {ro}")
            how = '정상(정제후)'
    if juso:
        j = juso[0]
        res.update({'검증결과': how, '정규주소': j.get('roadAddr', ''), '우편번호': j.get('zipNo', ''),
                    'juso시도': j.get('siNm', ''), 'juso시군구': j.get('sggNm', ''),
                    '행정동': j.get('emdNm', ''), '건물명': j.get('bdNm', '')})
        if r['시군구'] and j.get('sggNm') and r['시군구'] not in j.get('sggNm', '') and j.get('sggNm') not in r['시군구']:
            res['비고'] = f"시군구 불일치(원천 {r['시군구']} / 주소DB {j.get('sggNm')})"
    else:
        res['검증결과'] = '조회실패' if err else '주소없음'
        res['비고'] = err
    return res


m = pd.read_csv('data/processed/goodprice_master.csv', dtype=str).fillna('')
print('대상', len(m))
t0 = time.time(); rows = []
with ThreadPoolExecutor(max_workers=WORKERS) as ex:
    for n, rec in enumerate(ex.map(check, (r for _, r in m.iterrows())), 1):
        rows.append(rec)
        if n % 500 == 0:
            pd.DataFrame(rows).to_csv('data/processed/address_check.csv', index=False, encoding='utf-8-sig')
            el = time.time() - t0
            print(f'{n}/{len(m)} ({el/60:.1f}분, 남은 {el/n*(len(m)-n)/60:.0f}분)', flush=True)

df = pd.DataFrame(rows)
df.to_csv('data/processed/address_check.csv', index=False, encoding='utf-8-sig')
print('검증결과', df.검증결과.value_counts().to_dict())
print('시군구 불일치', (df.비고.str.startswith('시군구 불일치')).sum())
