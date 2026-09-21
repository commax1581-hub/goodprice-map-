"""착한가격업소 마스터 데이터 생성
- 공공데이터포털 CSV(기준 목록) + goodprice.go.kr 지도데이터(좌표·업소번호·세부업종) + goodprice 엑셀(편의시설·이미지)
- 결과: data/processed/goodprice_master.csv / .json, data/processed/match_report.json
"""
import json, re, difflib, html
from pathlib import Path
import pandas as pd

RAW = Path('data/raw')
OUT = Path('data/processed'); OUT.mkdir(parents=True, exist_ok=True)
STAMP = '2026-09-19'

SIDO_ALIAS = {'서울': '서울특별시', '부산': '부산광역시', '대구': '대구광역시', '인천': '인천광역시',
              '광주': '전남광주통합특별시', '광주광역시': '전남광주통합특별시', '전라남도': '전남광주통합특별시', '전남': '전남광주통합특별시',
              '대전': '대전광역시', '울산': '울산광역시', '세종': '세종특별자치시', '경기': '경기도',
              '강원': '강원특별자치도', '강원도': '강원특별자치도', '충북': '충청북도', '충남': '충청남도',
              '전북': '전북특별자치도', '전라북도': '전북특별자치도', '경북': '경상북도', '경남': '경상남도',
              '제주': '제주특별자치도', '제주도': '제주특별자치도'}
SIDO_SET = set(SIDO_ALIAS.values())

FAC = [  # (엑셀 컬럼, 코드, 표시명)
    ('주차여부', 'F01', '주차'), ('포장여부', 'F02', '포장'), ('배달여부', 'F03', '배달'), ('예약여부', 'F04', '예약'),
    ('남여화장실 구분여부', 'F05', '남/여 화장실 구분'), ('단체이용 가능여부', 'F06', '단체이용 가능'),
    ('무선인터넷 제공여부', 'F07', '무선인터넷'), ('반려동물 동반여부', 'F08', '반려동물 동반'),
    ('유아시설여부', 'F09', '유아시설'), ('장애인 편의시설여부', 'F10', '장애인 편의시설'),
    ('임산부 우대여부', 'F11', '임산부 우대'), ('지역화폐(지류형)', 'F12', '지역화폐(지류)'),
    ('지역화폐(모바일형)', 'F13', '지역화폐(모바일)'), ('지역화폐(카드형)', 'F14', '지역화폐(카드)')]


def nname(s):
    s = re.sub(r'㈜|\(주\)|주식회사', '', str(s or ''))
    return re.sub(r'[\s\W_]+', '', s).lower()


ROAD_RE = re.compile(r'([가-힣A-Za-z0-9·.]+?(?:로|길))\s*(?:(\d+)\s*(번?길))?\s*(?:지하\s*)?(\d+(?:-\d+)?)')


def road(s):
    s = re.sub(r'\([^)]*\)', ' ', str(s or ''))
    toks = s.split()
    # 시도·시군구 토큰 제거 후 도로명+건물번호 추출
    body = ' '.join(t for t in toks if not re.search(r'(특별시|광역시|특별자치시|도|시|군|구)$', t) or re.search(r'(로|길)$', t))
    m = ROAD_RE.search(body)
    if not m:
        return re.sub(r'\s+', '', s)
    return m.group(1) + (m.group(2) + m.group(3) if m.group(2) else '') + m.group(4)


def sido_of(addr):
    t = str(addr or '').split()
    if not t:
        return ''
    if t[0] in SIDO_SET:
        return t[0]
    for k, v in SIDO_ALIAS.items():
        if t[0].startswith(k):
            return v
    return ''


def sgg_of(addr):
    t = str(addr or '').split()
    return t[1] if len(t) > 1 else ''


def to_int(v):
    try:
        return int(float(str(v).replace(',', '')))
    except (ValueError, TypeError):
        return None


# ---------- 로드 ----------
csv = pd.read_csv(RAW / 'datagokr_goodprice.csv', dtype=str, encoding='cp949').fillna('')
xl = pd.read_excel(RAW / f'goodprice_excel_전국_{STAMP}.xls', header=2, dtype=str).fillna('')
mp = pd.DataFrame(json.load(open(RAW / f'goodprice_map_{STAMP}.json', encoding='utf-8'))['items']).fillna('')


def unesc(v):  # 지도데이터는 &amp;amp; 처럼 이중 이스케이프됨
    v = str(v)
    for _ in range(3):
        v = html.unescape(v)
    return v


for d in (csv, xl, mp):
    for col in d.columns:
        if pd.api.types.is_string_dtype(d[col]) or d[col].dtype == object:
            d[col] = d[col].map(unesc)

for d, n, a in [(csv, '업소명', '주소'), (xl, '업소명', '주소'), (mp, 'bsshNm', 'roadNmAddr')]:
    d['k_name'] = d[n].map(nname)
    d['k_road'] = d[a].map(road)
    d['key'] = d.k_name + '|' + d.k_road

# ---------- 1) 사이트 내부 결합: 엑셀(12,900) ⨝ 지도(좌표) ----------
mp_by_key = {}
for i, r in mp.iterrows():
    mp_by_key.setdefault(r.key, []).append(i)
used_mp = set()
xl['mp_idx'] = None
for i, r in xl.iterrows():
    for j in mp_by_key.get(r.key, []):
        if j not in used_mp:
            xl.at[i, 'mp_idx'] = j; used_mp.add(j); break
# 이름 동일 + 같은 시도에서 유일한 경우 보조 결합
mp['sido'] = mp.ctpvNm
xl['sido'] = xl['주소'].map(sido_of)
for i, r in xl[xl.mp_idx.isna()].iterrows():
    c = mp[(mp.k_name == r.k_name) & (mp.sido == r.sido) & (~mp.index.isin(used_mp))]
    if len(c) == 1:
        xl.at[i, 'mp_idx'] = c.index[0]; used_mp.add(c.index[0])

site = xl.copy()
for col in ['bsshSn', 'indutyCd', 'indutyNm', 'lat', 'lot', 'roadNmAddr', 'ctpvNm']:
    site[col] = site.mp_idx.map(lambda j: mp.at[j, col] if j is not None and pd.notna(j) else '')
site['sido'] = site.apply(lambda r: r.ctpvNm or r.sido, axis=1)
site['sgg'] = site['주소'].map(sgg_of)
site_only_map = mp[~mp.index.isin(used_mp)]  # 엑셀엔 없고 지도에만 있는 업소

# ---------- 2) 공공데이터 CSV ⨝ 사이트 ----------
csv['sido'] = csv['시도'].map(lambda s: SIDO_ALIAS.get(s, s))
csv['sgg'] = csv['시군'].where(csv['시군'] != '', csv['주소'].map(sgg_of))
site_by_key = {}
for i, r in site.iterrows():
    site_by_key.setdefault(r.key, []).append(i)
used_site = set()
csv['site_idx'] = None
csv['매칭방법'] = ''


def take(i, j, how):
    csv.at[i, 'site_idx'] = j; csv.at[i, '매칭방법'] = how; used_site.add(j)


for i, r in csv.iterrows():  # T1 업소명+도로명주소 일치
    for j in site_by_key.get(r.key, []):
        if j not in used_site:
            take(i, j, 'T1_업소명+주소'); break
for i, r in csv[csv.site_idx.isna()].iterrows():  # T2 업소명 일치 + 같은 시도·시군구 유일
    c = site[(site.k_name == r.k_name) & (site.sido == r.sido) & (site.sgg == r.sgg) & (~site.index.isin(used_site))]
    if len(c) == 1:
        take(i, c.index[0], 'T2_업소명+시군구(주소상이)')
for i, r in csv[csv.site_idx.isna()].iterrows():  # T3 도로명주소 일치 + 업소명 유사
    c = site[(site.k_road == r.k_road) & (site.sido == r.sido) & (~site.index.isin(used_site))]
    if len(c):
        sc = c.k_name.map(lambda n: difflib.SequenceMatcher(None, n, r.k_name).ratio())
        if sc.max() >= 0.5 and (sc >= 0.5).sum() == 1:
            take(i, sc.idxmax(), f'T3_주소+업소명유사({sc.max():.2f})')

# ---------- 3) 마스터 조립 ----------
rows = []


def fac_flags(src):
    return {code: ('Y' if str(src.get(col, '')).strip().upper() == 'O' else 'N') for col, code, _ in FAC}


def base_site_fields(s):
    return {
        '사이트업소번호': s['bsshSn'], '세부업종': s['indutyNm'], '업종코드': s['indutyCd'],
        '위도': s['lat'], '경도': s['lot'], '좌표출처': 'goodprice' if s['lat'] else '',
        '이미지수': sum(1 for k in ('이미지1', '이미지2', '이미지3') if s.get(k, '')),
        '사이트대표메뉴': s['주요품목'], '사이트대표가격': to_int(s['가격']),
        **fac_flags(s)}


for i, r in csv.iterrows():
    rec = {'출처': '공공데이터+사이트' if r.site_idx is not None and pd.notna(r.site_idx) else '공공데이터만',
           '매칭방법': r['매칭방법'] or '미매칭',
           '시도': r.sido, '원천시도': r['시도'], '시군구': r.sgg, '업종': r['업종'], '업소명': r['업소명'],
           '주소': r['주소'], '전화번호': r['연락처']}
    for k in range(1, 5):
        rec[f'메뉴{k}'] = r[f'메뉴{k}']; rec[f'가격{k}'] = to_int(r[f'가격{k}'])
    if rec['출처'] == '공공데이터+사이트':
        rec.update(base_site_fields(site.loc[r.site_idx]))
    rows.append(rec)

for j, s in site[~site.index.isin(used_site)].iterrows():
    rec = {'출처': '사이트만', '매칭방법': '-', '시도': s['sido'], '원천시도': '', '시군구': s['sgg'],
           '업종': s['업종명'], '업소명': s['업소명'], '주소': s['주소'], '전화번호': s['업소 전화번호'],
           '메뉴1': s['주요품목'], '가격1': to_int(s['가격'])}
    rec.update(base_site_fields(s))
    rows.append(rec)

for j, s in site_only_map.iterrows():  # 지도에만 있는 업소(엑셀 미포함)
    rec = {'출처': '사이트만(지도)', '매칭방법': '-', '시도': s.ctpvNm, '원천시도': '', '시군구': sgg_of(s.roadNmAddr),
           '업종': s.indutyNm.split('_')[0], '업소명': s.bsshNm, '주소': s.roadNmAddr, '전화번호': '',
           '메뉴1': s.menuNm, '가격1': to_int(s.menuPc), '사이트업소번호': s.bsshSn, '세부업종': s.indutyNm,
           '업종코드': s.indutyCd, '위도': s.lat, '경도': s.lot, '좌표출처': 'goodprice',
           '사이트대표메뉴': s.menuNm, '사이트대표가격': to_int(s.menuPc)}
    rows.append(rec)

REGISTRY = OUT / 'id_registry.json'   # 관리번호 대장: 한 번 준 번호는 영구 유지(저장·공유 링크·검증 캐시 보호)


def id_keys(r):
    """같은 업소를 알아보는 기준: 공식 사이트 업소번호 → 시도+업소명+주소"""
    keys = []
    sn = str(r.get('사이트업소번호') or '').strip()
    if sn and sn != 'nan':
        keys.append('sn:' + sn)
    keys.append('na:' + '|'.join(re.sub(r'\s+', ' ', str(r.get(k) or '')).strip() for k in ('시도', '업소명', '주소')))
    return keys


def assign_ids(df):
    reg = json.load(open(REGISTRY, encoding='utf-8')) if REGISTRY.exists() else {}
    nxt = max([int(v[2:]) for v in reg.values()] or [0]) + 1
    used, ids = set(), []
    for _, r in df.iterrows():
        keys = id_keys(r)
        gid = next((reg[k] for k in keys if k in reg and reg[k] not in used), None)
        if gid is None:                              # 새로 지정된 업소 → 새 번호
            gid = f'GP{nxt:05d}'; nxt += 1
        used.add(gid); ids.append(gid)
        for k in keys:
            reg[k] = gid
    json.dump(reg, open(REGISTRY, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    return ids


master = pd.DataFrame(rows)
for _, code, _ in FAC:
    master[code] = master[code].fillna('N') if code in master else 'N'
master['좌표출처'] = master['좌표출처'].fillna('').replace('', '미확보')
master = master.sort_values(['시도', '시군구', '업소명'], kind='stable').reset_index(drop=True)
master.insert(0, '관리번호', assign_ids(master))

master.to_csv(OUT / 'goodprice_master.csv', index=False, encoding='utf-8-sig')
master.to_json(OUT / 'goodprice_master.json', orient='records', force_ascii=False)

report = {
    'stamp': STAMP,
    'inputs': {'datagokr_csv': len(csv), 'site_excel': len(xl), 'site_map': len(mp)},
    'site_excel_with_coords': int(site.lat.ne('').sum()),
    'site_map_not_in_excel': len(site_only_map),
    'csv_match': master[master.출처.str.startswith('공공데이터')].매칭방법.str.split('(').str[0].value_counts().to_dict(),
    'source_counts': master.출처.value_counts().to_dict(),
    'coords': master.좌표출처.value_counts().to_dict(),
    'master_rows': len(master)}
json.dump(report, open(OUT / 'match_report.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
json.dump([{'code': c, 'column': col, 'label': l} for col, c, l in FAC],
          open(OUT / 'facility_codes.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
print(json.dumps(report, ensure_ascii=False, indent=2))
