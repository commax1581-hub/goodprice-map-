"""소상공인 상가(상권)정보 대사 — 전국 파일로 착한가격업소 ↔ 상가업소 연결 (근거용, 판정 아님)
준비: 공공데이터포털 '소상공인시장진흥공단_상가(상권)정보' 전국 파일(zip)을 내려받아 data/raw/sbiz/ 에 풀어 둔다(CSV 여러 개).
     원본은 크고 다시 받을 수 있으므로 비공개 백업에서 제외한다(backup_data.py).
방법: 같은 건물(건물관리번호, 없으면 도로명+건물번호) 안에서 업소명 유사도가 가장 높은 상가를 연결. 층이 같으면 가산.
결과: data/processed/sbiz_link.csv (관리번호, 상가업소번호, 상가상호, 상가층, 유사도, 같은층, 파일기준일, 확인일)
쓰임: diff_update.py — 신규·업체명 변경·이전의 뒷받침, 지난 분기엔 연결됐는데 사라지면 '폐업 의심'(확인 목록)
설계: docs/공공데이터-파이프라인.md 7장·8장
"""
import difflib, glob, re, sys
from datetime import date
from pathlib import Path
import pandas as pd
import addr_util as A

ROOT = Path(__file__).parent
SRC = ROOT / 'data' / 'raw' / 'sbiz'
OUT = ROOT / 'data' / 'processed' / 'sbiz_link.csv'
WANT = ['상가업소번호', '상호명', '지점명', '상권업종대분류코드', '상권업종소분류명', '건물관리번호', '도로명주소', '층정보', '경도', '위도']
# 우리 업종 → 상가정보 업종 대분류(업종코드 파일 data/raw/sbiz_업종코드_*.csv 기준): I2 음식점업, I1 숙박업, S2 수리 및 개인 서비스업
EXPECT = {'한식': 'I2', '중식': 'I2', '일식': 'I2', '양식': 'I2', '베이커리': 'I2', '기타요식업': 'I2',
          '숙박업': 'I1', '미용업': 'S2', '이용업': 'S2', '세탁업': 'S2', '목욕업': 'S2'}   # 기타비요식업은 제한 없음
MIN_SIM = 0.5

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')


def nname(s):
    s = re.sub(r'㈜|\(주\)|주식회사', '', str(s or ''))
    return re.sub(r'[\s\W_]+', '', s).lower()


def sim(a, b):
    a, b = nname(a), nname(b)
    if not a or not b:
        return 0.0
    if a in b or b in a:                       # '송이향' ⊂ '송이향칼국수전문점'
        return max(0.85, difflib.SequenceMatcher(None, a, b).ratio())
    return difflib.SequenceMatcher(None, a, b).ratio()


def floor_num(s):
    m = re.search(r'(지하|B)?\s*(\d+)', str(s or ''))
    return ('-' if m and m.group(1) else '') + m.group(2) if m else ''


files = sorted(glob.glob(str(SRC / '*.csv')))
if not files:
    print(f'상가정보 파일이 없습니다 → 공공데이터포털에서 전국 파일을 받아 {SRC.relative_to(ROOT)}/ 에 풀어 주세요'); sys.exit(1)
stamp = (re.findall(r'_(20\d{4,6})\.csv', ' '.join(files)) or [''])[-1]      # 파일 이름의 기준 연월(예: 202606)

m = pd.read_csv(ROOT / 'data/processed/goodprice_master.csv', dtype=str).fillna('')
ad = pd.read_csv(ROOT / 'data/processed/address_check.csv', dtype=str).fillna('').set_index('관리번호')
m['bd'] = m['관리번호'].map(ad['건물관리번호']).fillna('')
m['rk'] = m['주소'].map(A.road_key)
m['fl'] = m['주소'].map(lambda a: floor_num(A.floor_of(a)))
bds, rks = set(m.bd) - {''}, set(m.rk) - {''}

# 파일은 수백만 줄이라 우리 업소가 있는 건물만 남기며 나눠 읽는다
keep, cols_seen = [], None
for f in files:
    for enc in ('utf-8', 'cp949'):
        try:
            head = pd.read_csv(f, nrows=0, encoding=enc)
            break
        except UnicodeDecodeError:
            continue
    use = [c for c in WANT if c in head.columns]
    cols_seen = cols_seen or use
    for ch in pd.read_csv(f, dtype=str, encoding=enc, usecols=use, chunksize=200_000):
        ch = ch.fillna('')
        ch['rk'] = ch['도로명주소'].map(A.road_key) if '도로명주소' in ch else ''
        mask = ch['건물관리번호'].isin(bds) if '건물관리번호' in ch else False
        mask = mask | ch['rk'].isin(rks)
        keep.append(ch[mask])
sb = pd.concat(keep, ignore_index=True) if keep else pd.DataFrame(columns=WANT + ['rk'])
print(f'파일 {len(files)}개 · 기준일 {stamp or "?"} · 항목 {cols_seen} · 우리 건물의 상가 {len(sb):,}곳')
if '건물관리번호' not in sb:
    print('주의: 파일에 건물관리번호가 없어 도로명+건물번호로만 대조합니다')

by_bd = {k: g for k, g in sb.groupby('건물관리번호')} if '건물관리번호' in sb else {}
by_rk = {k: g for k, g in sb.groupby('rk')}
rows = []
for _, r in m.iterrows():
    cand = by_bd.get(r.bd) if r.bd and r.bd in by_bd else by_rk.get(r.rk)
    if cand is None or not len(cand):
        continue
    best, bs = None, 0.0
    for _, c in cand.iterrows():
        s = max(sim(r['업소명'], c['상호명']), sim(r['업소명'], (c['상호명'] + c.get('지점명', ''))))
        same_fl = bool(r.fl) and r.fl == floor_num(c.get('층정보', ''))
        want, got = EXPECT.get(r['업종']), c.get('상권업종대분류코드', '')
        if want and got and want != got and s < 0.85:     # 업종이 다르면 이름이 아주 비슷할 때만(미용실 ↔ 같은 건물 식당 오연결 방지)
            continue
        s2 = s + (0.05 if same_fl else 0) + (0.05 if want and got == want else 0)
        if s2 > bs:
            best, bs = (c, s, same_fl), s2
    if best and best[1] >= MIN_SIM:
        c, s, same_fl = best
        rows.append({'관리번호': r['관리번호'], '상가업소번호': c.get('상가업소번호', ''), '상가상호': c['상호명'],
                     '상가업종': c.get('상권업종소분류명', ''), '상가층': c.get('층정보', ''), '유사도': round(s, 2), '같은층': 'Y' if same_fl else '',
                     '파일기준일': stamp, '확인일': date.today().isoformat()})
out = pd.DataFrame(rows, columns=['관리번호', '상가업소번호', '상가상호', '상가업종', '상가층', '유사도', '같은층', '파일기준일', '확인일'])
out.to_csv(OUT, index=False, encoding='utf-8-sig')
print(f'연결 {len(out):,} / {len(m):,}곳 ({len(out) / max(len(m), 1) * 100:.1f}%) → {OUT.relative_to(ROOT)}')
