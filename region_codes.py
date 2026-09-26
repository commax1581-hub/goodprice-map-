"""정제 결과에 행정구역 코드 칸을 붙인다 — 시군구코드 · 필터코드 · 법정동코드 · 건물관리번호 · 코드출처
공통 기준: ../공통지식/기준자료/행정구역 (행정구역_시군구.csv · regions.py). API 호출 없음.

순서(버그이력 #58):
 1) 주소 정제 결과(address_check.csv, 주소 캐시에서 나옴)의 juso 시도·시군구 **이름**(2026-09 조회, 현재 이름) → 코드표에서 코드   ← 주 경로
 2) 캐시에 이름이 없으면 원문 시군구 → regions.codes_of(시군구, 힌트=시도)
    옛 이름 하나가 새 구 여럿(인천 중구·서구)이면 원문 주소를 넘겨 공통 읍면동표(행정구역_읍면동.csv)로 가르고,
    표로 못 가르면(동 없는 도로명 주소) INCHEON_SPLIT로 — 코드출처 '원문이름+읍면동표' / '원문이름+기존규칙'
 - 건물관리번호 앞자리는 **발급 당시 코드**다(강원 42·전북 45·전남 46·광주 29·남구 28170 …, 캐시의 20%).
   코드를 잘라 쓰지 않고, 앞 5자리가 1)·2)로 얻은 시군구코드와 같을 때만 앞 10자리를 법정동코드로 쓴다.
 - 필터코드: 앱이 시군구를 고르는 단위. 일반구가 있는 시(수원시 장안구 등)는 시 코드로 묶는다. 세종은 단층이라 '36110:읍면동'.

단독 실행: python region_codes.py  → data/processed/app_data.json·csv에 칸을 붙이고 결과 수치를 출력
"""
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).parent
REG_DIR = (ROOT / '../공통지식/기준자료/행정구역').resolve()
sys.path.insert(0, str(REG_DIR))
from regions import codes_of, sido_code  # noqa: E402

CHECK = ROOT / 'data/processed/address_check.csv'   # 주소 정제 단계 결과(관리번호별, 수기 보정 반영) — addr_util 캐시에서 나온 것
COLS = ['시군구코드', '필터코드', '법정동코드', '건물관리번호', '코드출처']

# 인천 행정체제 개편(2026-06-30): 공통 읍면동표로 못 가른 행의 대체 수단(H17). 읍면동 또는 검단 안에만 있는 도로명.
# 2026-09-26 좌표로 검증: 영종 14곳 전부 경도 126.567 서쪽, 제물포 70곳 126.599 동쪽, 검단 10곳 위도 37.588 북쪽.
# 동이 안 적힌 '서구 완정로31'이 서해구로 갔다가 좌표로 걸러져 완정로를 더함.
INCHEON_SPLIT = {
    ('28', '중구'): (r'영종|운서|운남|운북|중산|용유|을왕|남북|덕교|무의', '28155', '28125'),   # 영종도·용유도 → 영종구, 나머지 → 제물포구
    ('28', '서구'): (r'검단|불로|대곡|마전|당하|원당|오류|왕길|금곡|아라|백석|완정로', '28290', '28275'),  # 검단 → 검단구, 나머지 → 서해구
}


def load_table():
    rows = list(csv.DictReader(open(REG_DIR / '행정구역_시군구.csv', encoding='utf-8-sig')))
    by_name = {(r['시도코드'], r['시군구명'].replace(' ', '')): r['시군구코드'] for r in rows}
    name_of = {r['시군구코드']: r['시군구명'] for r in rows}
    # 일반구 → 부모 시: '수원시장안구' → '수원시'(같은 시도에 부모 이름이 있을 때만)
    parent = {}
    for r in rows:
        m = re.match(r'^(.+?시)(.+구)$', r['시군구명'])
        if m and (r['시도코드'], m[1]) in by_name:
            parent[r['시군구코드']] = by_name[(r['시도코드'], m[1])]
    return by_name, name_of, parent


def pretty(name):
    """'수원시장안구' → '수원시 장안구'(코드표는 붙여 쓴다)"""
    return re.sub(r'^(.+?시)(.+구)$', r'\1 \2', name)


def load_check():
    with open(CHECK, encoding='utf-8-sig') as f:
        return {r['관리번호']: r for r in csv.DictReader(f)}


def attach(rows, check=None):
    """rows: dict 목록(관리번호·시도·시군구·행정동·주소 칸). 각 행에 COLS를 붙이고 출처별 개수를 돌려준다."""
    check = check if check is not None else load_check()
    by_name, name_of, parent = load_table()
    cnt = Counter()
    for r in rows:
        sd = sido_code(r['시도'])
        c = check.get(r['관리번호']) or {}
        if c.get('juso시도') and sido_code(c['juso시도']) != sd:
            # 주소 DB가 다른 시도의 같은 도로명을 잡은 경우(정제후 재조회가 시도 없이 '동구 중앙로 15'로 찾음, GP09569 인천 → 광주) — 버리고 원문으로
            cnt['주소DB 시도 불일치(버림)'] += 1
            c = {}
        bd = c.get('건물관리번호', '') if len(c.get('건물관리번호', '')) == 25 else ''
        code, src = '', ''
        jsg = (c.get('juso시군구') or '').replace(' ', '')
        if jsg:
            code = by_name.get((sido_code(c.get('juso시도', '')) or sd, jsg), '')
            src = '주소DB이름' if code else ''
        if not code and sd == '36':
            code, src = '36110', '세종단층'
        if not code:
            g = r['시군구']
            got = codes_of(g, 힌트=r['시도'])['시군구']
            if len(got) == 1:
                code, src = got[0], '원문이름'
            elif len(got) > 1:
                # 옛 이름 하나가 새 구 여럿(인천 중구·서구): 원문 주소를 함께 넘기면 공통 읍면동표로 하나를 고른다(H17).
                # 결과는 옛 이름의 후보 안에 있어야 한다 — 주소 속 다른 낱말이 시군구로 읽혀 엉뚱한 코드가 오면 버린다.
                by_dong = codes_of(f"{r['시도']} {g} {r['주소']} {r.get('행정동', '')}", 힌트=r['시도'])['시군구']
                if len(by_dong) == 1 and by_dong[0] in got:
                    code, src = by_dong[0], '원문이름+읍면동표'
                elif (sd, g) in INCHEON_SPLIT:        # 표로 못 가른 것(동이 안 적힌 도로명 주소 등)만 기존 규칙
                    pat, hit, other = INCHEON_SPLIT[(sd, g)]
                    code, src = (hit if re.search(pat, r['주소'] + ' ' + r.get('행정동', '')) else other), '원문이름+기존규칙'
        if not code:
            src = '못정함'
        r['시군구코드'] = code
        r['필터코드'] = ('36110:' + (r.get('행정동') or '세종시')) if code == '36110' else parent.get(code, code)
        r['법정동코드'] = bd[:10] if bd and bd[:5] == code else ''
        r['건물관리번호'] = bd
        r['코드출처'] = src
        cnt[src] += 1
        if bd and bd[:5] != code:
            cnt['건물관리번호 앞자리가 옛 코드'] += 1
    return cnt


def filter_name(code, rows_name=None):
    """필터코드 → 화면 이름(현재 이름). 세종은 읍면동."""
    if code.startswith('36110:'):
        return code.split(':', 1)[1]
    _, name_of, _ = load_table()
    return pretty(name_of.get(code, ''))


if __name__ == '__main__':
    P = ROOT / 'data/processed/'
    rows = json.load(open(P / 'app_data.json', encoding='utf-8'))
    cnt = attach(rows)
    json.dump(rows, open(P / 'app_data.json', 'w', encoding='utf-8'), ensure_ascii=False)
    import pandas as pd
    pd.DataFrame(rows).drop(columns=['메뉴목록', '사진목록']).to_csv(P / 'app_data.csv', index=False, encoding='utf-8-sig')
    n = len(rows)
    print(f'{n:,}행')
    for k, v in cnt.most_common():
        print(f'  {k}: {v:,} ({v / n:.1%})')
    print('  법정동코드 채움:', f"{sum(1 for r in rows if r['법정동코드']):,}")
