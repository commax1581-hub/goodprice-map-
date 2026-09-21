"""원본·중간 데이터 비공개 백업 — 공개 저장소에서 제외한 파일을 별도 비공개 GitHub 저장소로 올린다.
대상: data/raw/, data/processed/, data/thumbs/, data/notices.json, 검수 엑셀(*.xlsx, *.xls) — 상가정보 전국 원본(data/raw/sbiz/)은 제외
제외: API 키 파일(.env, API키.txt, .dev.vars) — 복사 전에 키 문자열이 들어간 파일이 없는지 검사하고, 있으면 중단한다.
올리기 전에 백업 저장소가 로그인 없이 보이는지(공개인지) 확인하고, 공개면 중단한다.
실행: python backup_data.py            (복사 + 커밋 + push)
      python backup_data.py --no-push  (복사 + 커밋만)
백업 폴더: 프로젝트 폴더 옆 '착한식당-data-backup' (비공개 저장소 goodprice-map-data와 연결)
"""
import glob, os, shutil, subprocess, sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent
DEST = ROOT.parent / '착한식당-data-backup'
SOURCES = ['data/raw', 'data/processed', 'data/thumbs', 'data/notices.json', '*.xlsx', '*.xls']
EXCLUDE = ['data/raw/sbiz']          # 상가정보 전국 원본: 크고(GitHub 파일당 100MB 제한) 다시 받을 수 있음 → 연결표만 백업
KEY_FILES = ['.env', 'API키.txt', '.dev.vars']

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
