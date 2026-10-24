"""원본·중간 데이터 비공개 백업 — 공개 저장소에서 제외한 파일을 별도 비공개 GitHub 저장소로 올린다.
대상: data/raw/, data/processed/, data/thumbs/, data/notices.json, 검수 엑셀(*.xlsx, *.xls) — 상가정보 전국 원본(data/raw/sbiz/)은 제외
제외: API 키 파일(.env, API키.txt, .dev.vars) — 복사 전에 키 문자열이 들어간 파일이 없는지 검사하고, 있으면 중단한다.
올리기 전에 백업 저장소가 로그인 없이 보이는지(공개인지) 확인하고, 공개면 중단한다.
실행: python backup_data.py            (복사 + 커밋 + push + 구글 드라이브)
      python backup_data.py --no-push  (복사 + 커밋 + 구글 드라이브, push만 뺌)
      python backup_data.py --no-cloud (구글 드라이브만 뺌)
구글 드라이브(2026-10-24 추가, 장학금 방식): G:/내 드라이브/백업/착한식당/<날짜>/ 에 백업 저장소·코드 저장소 git bundle과 복구안내.md.
  날짜별 4벌 보관(5번째가 생기면 가장 오래된 것 삭제 — 드라이브 휴지통에 30일). G:가 없으면 건너뛴다. 키 파일은 원래 백업에 없어 올라가지 않는다.
  왜: 비공개 GitHub 한 곳뿐이면 계정·저장소 문제 때 캐시(재호출 수십만 회)와 번호 대장을 함께 잃는다 → 다른 회사 한 곳 더.
백업 폴더: 프로젝트 폴더 옆 '착한식당-data-backup' (비공개 저장소 goodprice-map-data와 연결)
"""
import glob, os, shutil, subprocess, sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent
DEST = ROOT.parent / '착한식당-data-backup'
SOURCES = ['data/raw', 'data/processed', 'data/thumbs', 'data/notices.json', '*.xlsx', '*.xls']
EXCLUDE = ['data/raw/sbiz', 'data/processed/_test_diff']          # 상가정보 전국 원본: 크고(GitHub 파일당 100MB 제한) 다시 받을 수 있음 → 연결표만 백업
KEY_FILES = ['.env', 'API키.txt', '.dev.vars']
CLOUD = Path('G:/내 드라이브') / '백업' / '착한식당'       # 구글 드라이브 데스크톱
KEEP_CLOUD = 4

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

def key_values():
    vals = []
    for f in KEY_FILES:
        p = ROOT / f
        if p.exists():
            for line in p.read_text(encoding='utf-8', errors='ignore').splitlines():
                v = line.split('=', 1)[-1].strip().strip('"\'')
                if len(v) >= 16: vals.append(v.encode())
    return vals

files = []
for s in SOURCES:
    for p in glob.glob(str(ROOT / s)):
        p = Path(p)
        files += [x for x in p.rglob('*') if x.is_file()] if p.is_dir() else [p]
files = [f for f in files if not any(f.relative_to(ROOT).as_posix().startswith(e) for e in EXCLUDE)]

keys = key_values()
leak = [f for f in files if any(k in f.read_bytes() for k in keys)]
if leak:
    print('중단: API 키 문자열이 들어간 파일이 있음 →', [str(f.relative_to(ROOT)) for f in leak])
    sys.exit(1)

if not (DEST / '.git').exists():
    DEST.mkdir(exist_ok=True)
    subprocess.run(['git', 'init', '-b', 'main'], cwd=DEST, check=True)
    (DEST / 'README.md').write_text('# 착한가격 지도 — 원본·중간 데이터 비공개 백업\n\n'
        '공개 저장소(goodprice-map-)에서 제외한 원본·검증 결과·검수 엑셀. **비공개 유지.** API 키는 넣지 않는다.\n'
        '복원: 이 폴더의 data/·엑셀을 프로젝트 폴더에 그대로 복사.\n', encoding='utf-8')

for f in files:
    dst = DEST / f.relative_to(ROOT)
    dst.parent.mkdir(parents=True, exist_ok=True)
    if not dst.exists() or dst.stat().st_size != f.stat().st_size or dst.stat().st_mtime < f.stat().st_mtime:
        shutil.copy2(f, dst)

subprocess.run(['git', 'add', '-A'], cwd=DEST, check=True)
changed = subprocess.run(['git', 'diff', '--cached', '--quiet'], cwd=DEST).returncode != 0
if changed:
    subprocess.run(['git', 'commit', '-q', '-m', f'백업 {datetime.now():%Y-%m-%d %H:%M}'], cwd=DEST, check=True)
print(f'파일 {len(files)}개 확인, 키 검사 통과, ' + ('새 커밋 생성' if changed else '바뀐 것 없음'))


def cloud_backup():
    """구글 드라이브에 git bundle 두 개(백업 저장소·코드 저장소) + 복구안내.md, 날짜별 4벌"""
    import re
    if not CLOUD.parents[1].exists():
        print('구글 드라이브(G:) 없음 → 클라우드 건너뜀')
        return True
    today = f'{datetime.now():%Y-%m-%d}'
    d = CLOUD / today
    d.mkdir(parents=True, exist_ok=True)
    ok = True
    # 공통지식도 함께: 착한가격 검사·행정구역 코드가 기대는데 원격이 없다(장학금 드라이브 백업은 주 1회라 그 사이 커밋이 빈다 — 2026-10-24 복구 시험)
    repos = [('착한식당-data', DEST), ('착한식당', ROOT)] + [('공통지식', p) for p in [ROOT.parent / '공통지식'] if (p / '.git').exists()]
    for name, repo in repos:
        out = d / f'{name}.bundle'
        r = subprocess.run(['git', '-C', str(repo), 'bundle', 'create', str(out), '--all'], capture_output=True, text=True)
        good = r.returncode == 0 and subprocess.run(['git', 'bundle', 'verify', str(out)], cwd=repo, capture_output=True).returncode == 0
        ok = ok and good
        print(f'  클라우드 {name}.bundle ' + ('됨(검증 통과)' if good else '실패 ' + (r.stderr or '')[-120:]))
    days = sorted(p.name for p in CLOUD.iterdir() if p.is_dir() and re.fullmatch(r'\d{4}-\d{2}-\d{2}', p.name))
    for old in days[:-KEEP_CLOUD]:
        shutil.rmtree(CLOUD / old, ignore_errors=True)
    days = days[-KEEP_CLOUD:]
    rows = [f"| {n} | {sum(x.stat().st_size for x in (CLOUD / n).rglob('*') if x.is_file()) / 1e6:,.0f}MB |" for n in reversed(days)]
    guide = ['# 착한가격 지도 — 구글 드라이브 백업', '',
             '`backup_data.py`가 만든다(날짜별 4벌). 키 파일(.env·API키.txt)은 없다 — 키는 각 콘솔에서 다시 받는다.', '',
             '## 되살리기',
             '1. 코드: `git clone 착한식당.bundle 착한식당` (공개 GitHub goodprice-map-에도 있다), 같은 폴더(착한식당 옆)에 `git clone 공통지식.bundle 공통지식` — 검사·행정구역 코드가 ../공통지식을 읽는다',
             '2. 데이터: `git clone 착한식당-data.bundle 착한식당-data-backup` → 그 안의 data/·엑셀을 프로젝트 폴더에 그대로 복사',
             '3. `.env`에 키를 넣고 `python check_data.py`로 확인', '',
             '## 지금 보관 중', '', '| 날짜 | 크기 |', '|---|---|'] + rows
    (CLOUD / '복구안내.md').write_text('\n'.join(guide) + '\n', encoding='utf-8')
    print(f'  클라우드 {d} · 보관 {len(days)}벌' + ('' if ok else ' — 실패한 bundle 있음'))
    return ok


if '--no-cloud' not in sys.argv and not cloud_backup():
    sys.exit(1)

if '--no-push' not in sys.argv:
    remote = subprocess.run(['git', 'remote'], cwd=DEST, capture_output=True, text=True).stdout.strip()
    if not remote:
        print('원격 저장소가 없음 → GitHub에 비공개 저장소를 만든 뒤: git -C "%s" remote add origin <주소>' % DEST)
        sys.exit(0)
    # 비공개 확인: 로그인 없이 저장소가 보이면(공개) 올리지 않는다
    import re, urllib.request, urllib.error
    url = subprocess.run(['git', 'remote', 'get-url', 'origin'], cwd=DEST, capture_output=True, text=True).stdout.strip()
    m = re.search(r'github\.com[/:]([^/]+/[^/.]+)', url)
    if m:
        try:
            urllib.request.urlopen(f'https://api.github.com/repos/{m.group(1)}', timeout=10)
            print('중단: 백업 저장소가 공개(Public) 상태입니다 → GitHub Settings에서 Private으로 바꾼 뒤 다시 실행')
            sys.exit(1)
        except urllib.error.HTTPError as e:
            if e.code != 404: print(f'경고: 공개 여부 확인 실패(HTTP {e.code}) — 계속 진행')
    subprocess.run(['git', 'push', '-q', '-u', 'origin', 'main'], cwd=DEST, check=True)
    print('비공개 저장소로 올림')
