"""변경 분류(diff_update.py) 시험 — 지금 데이터를 복사해 일부러 바꾼 '가짜 다음 분기'를 만들고, 기대한 대로 분류되는지 확인한다.
실행: python test_diff_update.py   (지금 데이터로 스냅숏이 없으면 먼저 만든다. 실제 데이터 파일은 건드리지 않는다)
시험 폴더: data/processed/_test_diff/ (끝나면 지워도 됨)
"""
import json, shutil, sys
from pathlib import Path
import pandas as pd
import diff_update as D

ROOT = Path(__file__).parent
T = ROOT / 'data' / 'processed' / '_test_diff'
PREV, CUR = T / 'prev', T / 'cur'
if T.exists():
    shutil.rmtree(T)
for d in (PREV, CUR):
    d.mkdir(parents=True)
    for f in D.FILES.values():
        if f.exists() and f.name != 'sbiz_link.csv':
            shutil.copy2(f, d / f.name)

m = pd.read_csv(CUR / 'goodprice_master.csv', dtype=str).fillna('')
ad = pd.read_csv(CUR / 'address_check.csv', dtype=str).fillna('')
kk = pd.read_csv(CUR / 'kakao_match.csv', dtype=str).fillna('')
det = json.load(open(CUR / 'goodprice_detail.json', encoding='utf-8'))
dsn = {d['bsshSn']: d for d in det}
adi = ad.set_index('관리번호')

has_sn = m[(m['사이트업소번호'] != '') & m['사이트업소번호'].isin(dsn)]
pick = iter(has_sn.sample(40, random_state=7)['관리번호'])
row = lambda gid: m.index[m['관리번호'] == gid][0]
expect = {}

# 1) 업체명 변경(공식 업소번호 같음) → 업체명 변경
g = next(pick); m.at[row(g), '업소명'] += '신장개업'; expect[g] = '업체명 변경'
# 2) 가격 변경
g = next(pick); d = dsn[m.at[row(g), '사이트업소번호']]
d['메뉴'] = [dict(x) for x in D.listval(d['메뉴'])] or [{'명': '시험메뉴', '가격': 1000, '지정': 'Y'}]
d['메뉴'][0]['가격'] = int(float(d['메뉴'][0]['가격'] or 0)) + 500; expect[g] = '세부정보 변경'
# 3) 영업시간 변경
g = next(pick); dsn[m.at[row(g), '사이트업소번호']]['영업시간'] = '07:07~21:21'; expect[g] = '세부정보 변경'
# 4) 전화 변경
g = next(pick); m.at[row(g), '전화번호'] = '02-000-0000'; expect[g] = '세부정보 변경'
# 5) 편의시설 변경
g = next(pick); m.at[row(g), 'F01'] = 'N' if m.at[row(g), 'F01'] == 'Y' else 'Y'; expect[g] = '세부정보 변경'
# 6) 이전: 다른 건물 주소·건물관리번호로
g, other = next(pick), next(pick)
m.at[row(g), '주소'] = m.at[row(other), '주소']
ad.loc[ad['관리번호'] == g, '건물관리번호'] = adi.at[other, '건물관리번호'] or 'TESTBD999'; expect[g] = '이전'
# 7) 같은 건물 층 이동 → 변경 없음
g = next(pick); m.at[row(g), '주소'] = D.re.sub(r'\s*\d+층', '', m.at[row(g), '주소']) + ' 3층'
if not adi.at[g, '건물관리번호']:
    ad.loc[ad['관리번호'] == g, '건물관리번호'] = 'TESTBD777'
    for df in (pd.read_csv(PREV / 'address_check.csv', dtype=str).fillna(''),):
        df.loc[df['관리번호'] == g, '건물관리번호'] = 'TESTBD777'; df.to_csv(PREV / 'address_check.csv', index=False, encoding='utf-8-sig')
expect[g] = '변경 없음'
# 8) 제외(지정 해제)
g = next(pick); m = m[m['관리번호'] != g]; expect[g] = '제외'
# 9) 추가(신규 지정)
new = m.iloc[0].copy(); new['관리번호'] = 'GP99901'; new['업소명'] = '시험신규분식'; new['사이트업소번호'] = '9999901'
new['주소'] = '서울특별시 종로구 시험로 1'; new['전화번호'] = '02-999-0001'
m = pd.concat([m, new.to_frame().T]); expect['GP99901'] = '추가'
# 10) 업소번호 없는 곳의 상호 변경 → 제외 1 + 추가 1 (같은 건물·같은 전화) = 제외+신규 짝
nosn = m[m['사이트업소번호'] == ''].iloc[0]; og = nosn['관리번호']
m = m[m['관리번호'] != og]
twin = nosn.copy(); twin['관리번호'] = 'GP99902'; twin['업소명'] = nosn['업소명'] + '새간판'
m = pd.concat([m, twin.to_frame().T]); expect[og] = '제외'; expect['GP99902'] = '추가'
ad = pd.concat([ad, ad[ad['관리번호'] == og].assign(관리번호='GP99902')])
# 11) 카카오 장소 ID 중복 → 매칭 검사
a, b = kk[kk['카카오장소ID'] != ''].iloc[:2]['관리번호']
kk.loc[kk['관리번호'] == b, '카카오장소ID'] = kk.loc[kk['관리번호'] == a, '카카오장소ID'].values[0]

m.to_csv(CUR / 'goodprice_master.csv', index=False, encoding='utf-8-sig')
ad.to_csv(CUR / 'address_check.csv', index=False, encoding='utf-8-sig')
kk.to_csv(CUR / 'kakao_match.csv', index=False, encoding='utf-8-sig')
json.dump(list(dsn.values()), open(CUR / 'goodprice_detail.json', 'w', encoding='utf-8'), ensure_ascii=False)

s, rematch = D.run(D.files_in(PREV), D.files_in(CUR), T / 'out')
cls = pd.read_csv(T / 'out' / 'classes.csv', dtype=str).set_index('관리번호')['분류']
rv = pd.read_csv(T / 'out' / 'review.csv', dtype=str).fillna('')
ok = True
for gid, want in expect.items():
    got = cls.get(gid, '(없음)')
    flag = '✓' if got == want else '✗'
    ok &= got == want
    print(f'{flag} {gid}: 기대 {want} / 결과 {got}')
checks = [('제외+신규 짝', (rv['유형'] == '제외+신규 짝').any()), ('카카오 중복 매칭 검사', rv['내용'].str.contains('곳에 연결').any()),
          ('검산', s['prev'] - s['drop'] == s['keep'] and s['keep'] + s['add'] == s['cur']),
          ('다시 매칭에 이전·추가·업체명 변경 포함', {k for k, v in expect.items() if v in ('이전', '추가', '업체명 변경')} <= set(rematch))]
for name, good in checks:
    print(('✓ ' if good else '✗ ') + name); ok &= bool(good)
print('항목별:', {k: v for k, v in s['items'].items() if v})
print('\n' + ('✅ 시험 통과' if ok else '❌ 시험 실패'))
sys.exit(0 if ok else 1)
