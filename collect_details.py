"""업소 상세 수집 — 영업시간 + 전체 메뉴 + 업소설명 + 담당부서
사이트 부담을 고려해 동시 3개, 요청 간 0.3초. 중단 시 이어서 진행.
결과: data/raw/goodprice_detail.json
실행: python collect_details.py --refresh  (분기 갱신: 전체 다시 수집 — 가격·메뉴·영업시간·사진 변경을 알기 위해)
      python collect_details.py            (이어서 진행: 오류 난 곳과 남은 곳만)
"""
import json, shutil, sys, time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import pandas as pd, requests

OUT = Path('data/raw/goodprice_detail.json')
URL = 'https://www.goodprice.go.kr/bssh/bsshInfo.json'
WORKERS, DELAY = 3, 0.3

s = requests.Session()
s.headers['User-Agent'] = 'Mozilla/5.0 (personal-study; goodprice map mashup)'

done = {}
if '--refresh' in sys.argv and OUT.exists():          # 지난 분기 결과는 비교용으로 남기고 전체 다시 수집
    shutil.copy2(OUT, OUT.with_name('goodprice_detail.prev.json'))
    OUT.unlink()
    print('전체 다시 수집(지난 결과 → goodprice_detail.prev.json)')
if OUT.exists():
    done = {d['bsshSn']: d for d in json.load(open(OUT, encoding='utf-8')) if not d.get('오류')}   # 오류 난 곳은 다시 시도
    print('이어서 진행: 완료', len(done))

m = pd.read_csv('data/processed/goodprice_master.csv', dtype=str).fillna('')
sn = [x for x in m[m.사이트업소번호 != ''].사이트업소번호.unique() if x not in done]
print('대상', len(sn))


def fetch(bsshSn):
    for _ in range(3):
        try:
            r = s.post(URL, files={'bsshSn': (None, bsshSn)}, timeout=15)
            if r.status_code == 200:
                j = r.json()
                res = j.get('result') or {}
                time.sleep(DELAY)
                return {'bsshSn': bsshSn,
                        '영업시간': (res.get('bsnHr') or '').strip(),
                        '업소설명': (res.get('bsshDc') or '').strip(),
                        '메뉴': [{'명': x.get('menuNm'), '가격': x.get('menuPc'), '지정': x.get('menuDsgnYn')}
                               for x in (j.get('menuList') or [])],
                        '담당부서': ((j.get('deptTelNo') or [{}])[0].get('deptNm') or ''),
                        '담당연락처': ((j.get('deptTelNo') or [{}])[0].get('deptTelNo') or ''),
                        '사진': [f"https://www.goodprice.go.kr/comm/showImageFile.do?fileCours=/bssh/{f.get('fileCours')}&fileId={f.get('thumnAtchFileOrginlNm')}"
                               for f in (j.get('fileList') or []) if f.get('fileCours')]}
        except Exception:
            pass
        time.sleep(1)
    return {'bsshSn': bsshSn, '영업시간': '', '업소설명': '', '메뉴': [], '담당부서': '', '담당연락처': '', '사진': [], '오류': True}


rows = list(done.values())
t0 = time.time()
with ThreadPoolExecutor(max_workers=WORKERS) as ex:
    for n, rec in enumerate(ex.map(fetch, sn), 1):
        rows.append(rec)
        if n % 500 == 0:
            json.dump(rows, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False)
            el = time.time() - t0
            print(f'{n}/{len(sn)} ({el/60:.1f}분, 남은 {el/n*(len(sn)-n)/60:.0f}분)', flush=True)

json.dump(rows, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False)
df = pd.DataFrame(rows)
print('완료', len(df), '| 영업시간 보유', (df.영업시간 != '').sum(), '| 메뉴 평균', df.메뉴.map(len).mean().round(2))
