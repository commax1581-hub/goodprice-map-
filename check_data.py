"""배포 전 데이터 자동 검사 — 버그이력(docs/버그이력.md)에서 나온 규칙을 매번 확인한다.
실패(FAIL)가 하나라도 있으면 종료코드 1 → 배포하지 않는다. 경고(WARN)는 확인만.
실행: python check_data.py            (검사만)
      python check_data.py --accept   (검사 통과 후, 이번 ID 목록을 다음 비교 기준으로 저장)
"""
import glob, json, re, sys
from pathlib import Path

ROOT = Path(__file__).parent
DATA = ROOT / 'app' / 'data'
REGISTRY = ROOT / 'data' / 'processed' / 'id_registry.json'
LAST = ROOT / 'data' / 'processed' / 'last_ids.json'        # 지난 배포 때의 ID 목록
UPJONG = {'한식', '중식', '일식', '양식', '베이커리', '기타요식업', '미용업', '이용업', '세탁업', '목욕업', '숙박업', '기타비요식업'}
TIME = re.compile(r'\d{2}:\d{2}')

fails, warns = [], []
def FAIL(msg, ex=None): fails.append(msg + (f'  예: {ex[:5]}' if ex else ''))
def WARN(msg, ex=None): warns.append(msg + (f'  예: {ex[:5]}' if ex else ''))

meta = json.load(open(DATA / 'index.json', encoding='utf-8'))
items, by_sido = [], {}
for f in sorted(glob.glob(str(DATA / '[0-9]*.json'))):
    code = Path(f).stem
    rows = json.load(open(f, encoding='utf-8'))
    by_sido[code] = rows
    for r in rows: r['_s'] = code
    items += rows

# 1. 건수·메타 일치
if meta['total'] != len(items): FAIL(f"index.json 총계 {meta['total']} ≠ 실제 {len(items)}")
for s in meta['sido']:
    if s['count'] != len(by_sido.get(s['code'], [])): FAIL(f"{s['name']} 건수 불일치")

# 2. ID: 중복 없음, 번호 대장에 등록, 지난 배포 대비 변동 (버그이력 #29)
ids = [i['i'] for i in items]
dup = sorted({x for x in ids if ids.count(x) > 1}) if len(set(ids)) != len(ids) else []
if dup: FAIL('ID 중복', dup)
reg_ids = set(json.load(open(REGISTRY, encoding='utf-8')).values()) if REGISTRY.exists() else set()
if not reg_ids: FAIL('번호 대장(id_registry.json) 없음 — 저장·공유 링크가 깨질 수 있음')
else:
    miss = [x for x in ids if x not in reg_ids]
    if miss: FAIL('번호 대장에 없는 ID', miss)
if LAST.exists():
    last = json.load(open(LAST, encoding='utf-8'))
    old, new = set(last['ids']), set(ids)
    gone, added = old - new, new - old
    print(f'지난 배포 대비: 유지 {len(old & new):,} / 빠짐 {len(gone):,} / 새로 {len(added):,}')
    if len(gone) > len(old) * 0.1: FAIL(f'지난 배포보다 {len(gone):,}곳 빠짐(10% 초과) — 원본 형식 변경 의심')
    # 같은 ID가 다른 가게를 가리키는지 (번호 밀림 감지)
    names = last.get('names', {})
    moved = [f"{x}:{names[x]}→{n}" for x, n in ((i['i'], i['n']) for i in items) if x in names and names[x] != n]
    if len(moved) > max(20, len(ids) * 0.01): FAIL(f'같은 ID의 업소명이 바뀐 곳 {len(moved)}건 — 번호 밀림 의심', moved)
    elif moved: WARN(f'업소명 변경 {len(moved)}건(상호 변경일 수 있음)', moved)

# 3. 필수값·형식
empty = [i['i'] for i in items if not (i.get('n') or '').strip() or not (i.get('a') or '').strip()]
if empty: FAIL('업소명·주소 빈 값', empty)
bad_u = sorted({i['u'] for i in items if i['u'] not in UPJONG})
if bad_u: FAIL('알 수 없는 업종(앱 필터에 없음)', bad_u)
tags = [i['n'] for i in items if re.search(r'[<>]', json.dumps([i['n'], i['a'], i['h'], i['m']], ensure_ascii=False))]
if tags: FAIL('화면에 태그로 해석될 문자 < > 포함 (버그이력 #23)', tags)

# 4. 좌표 (국내 범위)
out = [i['i'] for i in items if not (33.0 < i['y'] < 38.7 and 124.5 < i['x'] < 132.0)]
if out: FAIL('좌표가 국내 범위 밖', out)

# 5. 시군구 형식 (버그이력 #18)
for code, rows in by_sido.items():
    pat = r'(읍|면|동|세종시)$' if code == '36' else r'(시|군|구)$'
    bad = sorted({r['g'] for r in rows if not re.search(pat, r['g'] or '')})
    if bad: FAIL(f'{code} 시군구 형식 이상', bad)

# 6. 영업시간 (버그이력 #24)
same = [i['n'] for i in items if i['o'] and i['o'] == i['c']]
if same: FAIL('오픈=마감(24시간으로 잘못 표시됨)', same)
fmt = [(i['n'], i['o'], i['c']) for i in items if (i['o'] and not TIME.fullmatch(i['o'])) or (i['c'] and not TIME.fullmatch(i['c']))]
if fmt: FAIL('영업시간 형식 이상', fmt)
if any(bool(i['o']) != bool(i['c']) for i in items): FAIL('오픈·마감 중 하나만 있음')
badw = [i['w'] for i in items if i['w'] and not re.fullmatch(r'[0-6](,[0-6])*', i['w'])]
if badw: FAIL('휴무요일 형식 이상', badw)

# 7. 가격
neg = [i['n'] for i in items if i['p'] is not None and i['p'] <= 0]
if neg: FAIL('최저가격 0 이하', neg)
nop = sum(1 for i in items if i['p'] is None)
if nop > len(items) * 0.01: WARN(f'가격 없는 업소 {nop}곳')

# 8. 사진 축소본 (gen_thumbs.py)
thumbs = {p.stem for p in (ROOT / 'app' / 'thumbs').glob('*.webp')}
no_th = [i['i'] for i in items if i.get('img') and i['i'] not in thumbs]
if no_th: WARN(f'축소본 없는 사진 {len(no_th):,}장 → python gen_thumbs.py 실행(없으면 업종 아이콘으로 표시)', no_th)
orphan = thumbs - set(ids)
if orphan: WARN(f'데이터에 없는 축소본 {len(orphan)}개(gen_thumbs.py가 정리)')

# 9. 지역 해석 사전과 시도 목록 일치 (버그이력 #16)
intro = (ROOT / 'app' / 'intro.js').read_text(encoding='utf-8')
alias_codes = set(re.findall(r"'(\d{2})':\s*\[", intro[intro.find('SIDO_ALIAS'):intro.find('function buildRegionDict')]))
newc = [s['name'] for s in meta['sido'] if s['code'] not in alias_codes]
if newc: WARN('시도 줄임말 사전(intro.js SIDO_ALIAS)에 없는 시도 — 행정구역 변경 확인', newc)

# 결과
print(f"\n검사 대상 {len(items):,}곳 · 기준일 {meta.get('updated')}")
for w in warns: print('  WARN', w)
for f in fails: print('  FAIL', f)
if fails:
    print(f'\n❌ 실패 {len(fails)}건 — 배포하지 마세요.'); sys.exit(1)
print(f'\n✅ 통과 (경고 {len(warns)}건)')
if '--accept' in sys.argv:
    json.dump({'updated': meta.get('updated'), 'ids': ids, 'names': {i['i']: i['n'] for i in items}},
              open(LAST, 'w', encoding='utf-8'), ensure_ascii=False)
    print('이번 ID 목록을 다음 비교 기준으로 저장했습니다.')
