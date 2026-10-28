"""원본·중간 데이터 비공개 백업 — 공개 저장소에서 제외한 파일을 별도 비공개 GitHub 저장소와 구글 드라이브에 둔다.
대상: data/raw/, data/processed/, data/thumbs/, data/notices.json, 검수 엑셀(*.xlsx, *.xls) — 상가정보 전국 원본(data/raw/sbiz/)은 제외
제외: API 키 파일(.env, API키.txt, .dev.vars) — 복사 전에 키 문자열이 들어간 파일이 없는지 검사하고, 있으면 중단한다.
올리기 전에 백업 저장소가 로그인 없이 보이는지(공개인지) 확인하고, 공개면 중단한다.
실행: python backup_data.py            (복사 + 커밋 + 구글 드라이브 + push)
      python backup_data.py --no-push  (push만 뺌)
      python backup_data.py --no-cloud (구글 드라이브만 뺌)
      python backup_data.py --복구시험  (드라이브 최신판만으로 임시 폴더에 되살려 검사 — 아무것도 쓰거나 올리지 않음, 매월 1회)
구글 드라이브(2026-10-24 추가, 장학금 방식): G:/내 드라이브/백업/착한식당/<날짜>/ 에 백업 저장소·코드 저장소·공통지식 git bundle과 복구안내.md.
  날짜별 4벌 보관(5번째가 생기면 가장 오래된 것 삭제 — 드라이브 휴지통에 30일). G:가 없으면 건너뛴다. 키 파일은 원래 백업에 없어 올라가지 않는다.
  왜: 비공개 GitHub 한 곳뿐이면 계정·저장소 문제 때 캐시(재호출 수십만 회)와 번호 대장을 함께 잃는다 → 다른 회사 한 곳 더.
'다 만들고 검사한 뒤 바꿔 넣기'(2026-10-28, 장학금 사고 → 공통지식 모듈 공공데이터-파이프라인 백업 규칙):
  - 복사·bundle은 임시 이름(.part)에 쓰고, 내용 대조·verify를 통과한 뒤에만 os.replace로 진짜 이름에 넣는다.
    중간에 실패해도 앞서 만든 정상본을 덮지 않는다. 하나라도 실패하면 커밋하지 않고, 드라이브 4벌 정리도 하지 않는다.
  - 복사 전에 원본 내용을 검사한다(.json 읽힘 · 표·엑셀이 비어 있지 않음) — 갱신 도중의 깨진 파일이 '최신'으로 커밋되지 않게.
백업 폴더: 프로젝트 폴더 옆 '착한식당-data-backup' (비공개 저장소 goodprice-map-data와 연결)
"""
import glob, hashlib, json, os, re, shutil, subprocess, sys, tempfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent
DEST = ROOT.parent / '착한식당-data-backup'
SOURCES = ['data/raw', 'data/processed', 'data/thumbs', 'data/notices.json', '*.xlsx', '*.xls']
EXCLUDE = ['data/raw/sbiz', 'data/processed/_test_diff']          # 상가정보 전국 원본: 크고(GitHub 파일당 100MB 제한) 다시 받을 수 있음 → 연결표만 백업
KEY_FILES = ['.env', 'API키.txt', '.dev.vars']
CLOUD = Path('G:/내 드라이브') / '백업' / '착한식당'       # 구글 드라이브 데스크톱
KEEP_CLOUD = 4
JSON_FULL_MAX = 5 * 1024 * 1024                          # 이보다 큰 JSON은 처음·끝만 검사(메모리에 통째로 올리지 않는다 — 2026-10-28 39MB에서 MemoryError)

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


def source_files():
    files = []
    for s in SOURCES:
        for p in glob.glob(str(ROOT / s)):
            p = Path(p)
            files += [x for x in p.rglob('*') if x.is_file()] if p.is_dir() else [p]
    return [f for f in files if not any(f.relative_to(ROOT).as_posix().startswith(e) for e in EXCLUDE)]


def sha1(p, block=1 << 20):
    """조각으로 읽는 해시(큰 파일도 한 번에 메모리에 올리지 않는다)"""
    h = hashlib.sha1()
    with open(p, 'rb') as fh:
        for chunk in iter(lambda: fh.read(block), b''):
            h.update(chunk)
    return h.hexdigest()


def content_problem(p):
    """원본 내용 검사 — 문제가 있으면 이유, 없으면 None"""
    p = Path(p)
    if p.stat().st_size == 0:
        return '빈 파일'
    ext = p.suffix.lower()
    try:
        if ext == '.json' and p.stat().st_size <= JSON_FULL_MAX:
            with open(p, encoding='utf-8') as fh:
                json.load(fh)
        elif ext == '.json':                                 # 큰 JSON은 통째로 올리지 않고 처음·끝만(잘린 파일은 끝이 닫히지 않는다)
            with open(p, 'rb') as fh:
                head = fh.read(64).lstrip(b'\xef\xbb\xbf \t\r\n')
                fh.seek(-64, 2)
                tail = fh.read().rstrip(b' \t\r\n')
            if head[:1] not in (b'{', b'[') or tail[-1:] not in (b'}', b']'):
                return '처음·끝이 JSON 모양이 아님(잘림?)'
        elif ext == '.csv':
            with open(p, 'rb') as fh:
                if fh.read(1 << 20).count(b'\n') < 1:
                    return '줄바꿈 없음(잘림?)'
        elif ext == '.xlsx':
            with open(p, 'rb') as fh:
                if fh.read(2) != b'PK':
                    return '엑셀(xlsx) 형식 아님'
    except (ValueError, UnicodeDecodeError) as e:
        return f'읽히지 않음({type(e).__name__})'
    return None


def copy_files(files, dest):
    """.part에 복사 → 크기·해시 대조 → os.replace. (복사한 수, 실패 목록)"""
    n, fails = 0, []
    for f in files:
        dst = dest / f.relative_to(ROOT)
        if dst.exists() and dst.stat().st_size == f.stat().st_size and dst.stat().st_mtime >= f.stat().st_mtime:
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        part = dst.with_name(dst.name + '.part')
        try:
            shutil.copy2(f, part)
            if part.stat().st_size != f.stat().st_size or sha1(part) != sha1(f):
                raise IOError('복사본이 원본과 다름')
            os.replace(part, dst)
            n += 1
        except Exception as e:
            fails.append(f'{f.relative_to(ROOT).as_posix()}: {e}')
            part.unlink(missing_ok=True)
    return n, fails


def backup_repo():
    """비공개 백업 저장소에 복사·커밋. 실패하면 커밋하지 않고 False"""
    files = source_files()
    keys = key_values()
    leak = [f for f in files if any(k in f.read_bytes() for k in keys)]
    if leak:
        print('중단: API 키 문자열이 들어간 파일이 있음 →', [str(f.relative_to(ROOT)) for f in leak])
        return False
    bad = [(f, r) for f in files for r in [content_problem(f)] if r]
    if bad:
        print('중단: 내용이 깨진 원본이 있어 백업하지 않음(지난 정상본은 그대로) →',
              [f'{f.relative_to(ROOT).as_posix()}({r})' for f, r in bad[:10]])
        return False
    if not (DEST / '.git').exists():
        DEST.mkdir(exist_ok=True)
        subprocess.run(['git', 'init', '-b', 'main'], cwd=DEST, check=True)
        (DEST / 'README.md').write_text('# 착한가격 지도 — 원본·중간 데이터 비공개 백업\n\n'
            '공개 저장소(goodprice-map-)에서 제외한 원본·검증 결과·검수 엑셀. **비공개 유지.** API 키는 넣지 않는다.\n'
            '복원: 이 폴더의 data/·엑셀을 프로젝트 폴더에 그대로 복사.\n', encoding='utf-8')
    gi = DEST / '.gitignore'
    if '*.part' not in (gi.read_text(encoding='utf-8') if gi.exists() else ''):
        with open(gi, 'a', encoding='utf-8') as fh:
            fh.write('*.part\n')
    n, fails = copy_files(files, DEST)
    if fails:
        print(f'중단: 복사 실패 {len(fails)}건 — 커밋하지 않음(지난 정상본은 그대로) →', fails[:5])
        return False
    subprocess.run(['git', 'add', '-A'], cwd=DEST, check=True)       # 이 백업 전용 저장소에만 쓰는 스크립트(남의 파일 없음), .part는 .gitignore
    changed = subprocess.run(['git', 'diff', '--cached', '--quiet'], cwd=DEST).returncode != 0
    if changed:
        subprocess.run(['git', 'commit', '-q', '-m', f'백업 {datetime.now():%Y-%m-%d %H:%M}'], cwd=DEST, check=True)
    print(f'파일 {len(files)}개 확인(내용 검사·키 검사 통과), 새로 복사 {n}개, ' + ('새 커밋 생성' if changed else '바뀐 것 없음'))
    return True


def cloud_repos():
    return [('착한식당-data', DEST), ('착한식당', ROOT)] + \
           [('공통지식', p) for p in [ROOT.parent / '공통지식'] if (p / '.git').exists()]


def complete_days():
    """bundle이 다 갖춰진 날짜 폴더만(덜 된 날이 4벌 자리를 차지해 정상본을 밀어내지 않게)"""
    need = {f'{n}.bundle' for n, _ in cloud_repos()}
    return sorted(p.name for p in CLOUD.iterdir() if p.is_dir() and re.fullmatch(r'\d{4}-\d{2}-\d{2}', p.name)
                  and need <= {x.name for x in p.iterdir()})


def cloud_backup():
    """구글 드라이브에 git bundle(.part → verify → os.replace) + 복구안내.md, 다 갖춰진 날 기준 4벌"""
    if not CLOUD.parents[1].exists():
        print('구글 드라이브(G:) 없음 → 클라우드 건너뜀')
        return True
    today = f'{datetime.now():%Y-%m-%d}'
    d = CLOUD / today
    d.mkdir(parents=True, exist_ok=True)
    ok = True
    for name, repo in cloud_repos():
        out, part = d / f'{name}.bundle', d / f'{name}.bundle.part'
        part.unlink(missing_ok=True)
        r = subprocess.run(['git', '-C', str(repo), 'bundle', 'create', str(part), '--all'], capture_output=True, text=True, encoding='utf-8', errors='replace')
        good = r.returncode == 0 and part.exists() and \
            subprocess.run(['git', 'bundle', 'verify', str(part)], cwd=repo, capture_output=True).returncode == 0
        if good:
            os.replace(part, out)
        else:
            part.unlink(missing_ok=True)
            ok = False
        print(f'  클라우드 {name}.bundle ' + ('됨(검증 통과)' if good else '실패 — 그날 있던 정상본은 그대로 ' + (r.stderr or '')[-120:]))
    days = complete_days()
    if ok:
        for old in days[:-KEEP_CLOUD]:
            shutil.rmtree(CLOUD / old, ignore_errors=True)
        days = days[-KEEP_CLOUD:]
    else:
        print('  실패가 있어 오래된 벌은 지우지 않음')
    rows = [f"| {n} | {sum(x.stat().st_size for x in (CLOUD / n).rglob('*') if x.is_file()) / 1e6:,.0f}MB |" for n in reversed(days)]
    guide = ['# 착한가격 지도 — 구글 드라이브 백업', '',
             '`backup_data.py`가 만든다(날짜별 4벌, 다 갖춰진 날 기준). 키 파일(.env·API키.txt)은 없다 — 키는 각 콘솔에서 다시 받는다.',
             '되살려지는지는 매월 `python backup_data.py --복구시험`으로 확인한다.', '',
             '## 되살리기',
             '1. 코드: `git clone 착한식당.bundle 착한식당` (공개 GitHub goodprice-map-에도 있다), 같은 폴더(착한식당 옆)에 `git clone 공통지식.bundle 공통지식` — 검사·행정구역 코드가 ../공통지식을 읽는다',
             '2. 데이터: `git clone 착한식당-data.bundle 착한식당-data-backup` → 그 안의 data/·엑셀을 프로젝트 폴더에 그대로 복사',
             '3. `.env`에 키를 넣고 `python check_data.py`로 확인', '',
             '## 지금 보관 중', '', '| 날짜 | 크기 |', '|---|---|'] + rows
    tmp = CLOUD / '복구안내.md.part'
    tmp.write_text('\n'.join(guide) + '\n', encoding='utf-8')
    os.replace(tmp, CLOUD / '복구안내.md')
    print(f'  클라우드 {d} · 보관 {len(days)}벌' + ('' if ok else ' — 실패한 bundle 있음'))
    return ok


def push():
    remote = subprocess.run(['git', 'remote'], cwd=DEST, capture_output=True, text=True, encoding='utf-8', errors='replace').stdout.strip()
    if not remote:
        print('원격 저장소가 없음 → GitHub에 비공개 저장소를 만든 뒤: git -C "%s" remote add origin <주소>' % DEST)
        return True
    import urllib.request, urllib.error                                # 비공개 확인: 로그인 없이 보이면(공개) 올리지 않는다
    url = subprocess.run(['git', 'remote', 'get-url', 'origin'], cwd=DEST, capture_output=True, text=True, encoding='utf-8', errors='replace').stdout.strip()
    m = re.search(r'github\.com[/:]([^/]+/[^/.]+)', url)
    if m:
        try:
            urllib.request.urlopen(f'https://api.github.com/repos/{m.group(1)}', timeout=10)
            print('중단: 백업 저장소가 공개(Public) 상태입니다 → GitHub Settings에서 Private으로 바꾼 뒤 다시 실행')
            return False
        except urllib.error.HTTPError as e:
            if e.code != 404: print(f'경고: 공개 여부 확인 실패(HTTP {e.code}) — 계속 진행')
    subprocess.run(['git', 'push', '-q', '-u', 'origin', 'main'], cwd=DEST, check=True)
    print('비공개 저장소로 올림')
    return True


def restore_test():
    """드라이브 최신판(다 갖춰진 날)만으로 임시 폴더에 되살려 본다 — 쓰거나 올리는 것 없음. 통과면 True
    ① bundle 셋 clone ② 데이터를 코드 폴더에 복사 ③ check_data.py ④ build_web_data.py로 다시 만든 앱 데이터가 되살린 판과 같은가
    ⑤ 참고: 지금 프로젝트와 다른 데이터 파일 수(백업 뒤 바뀐 것 — 실패 아님)"""
    if not CLOUD.exists() or not complete_days():
        print('복구 시험: 드라이브에 다 갖춰진 백업이 없음'); return False
    day = complete_days()[-1]
    src = CLOUD / day
    tmp = Path(tempfile.mkdtemp(prefix='착한가격_복구시험_'))
    env = {**os.environ, 'PYTHONIOENCODING': 'utf-8'}
    ok, notes = True, []
    try:
        for name, folder in (('착한식당', '착한식당'), ('착한식당-data', 'data'), ('공통지식', '공통지식')):
            b = src / f'{name}.bundle'
            if not b.exists():
                continue
            r = subprocess.run(['git', 'clone', '-q', str(b), str(tmp / folder)], capture_output=True, text=True, encoding='utf-8', errors='replace')
            notes.append(f"clone {name} {'됨' if r.returncode == 0 else '실패'}")
            ok = ok and r.returncode == 0
        proj = tmp / '착한식당'
        for f in (tmp / 'data').rglob('*'):
            if f.is_file() and '.git' not in f.relative_to(tmp / 'data').parts and f.name not in ('README.md', '.gitignore'):
                t = proj / f.relative_to(tmp / 'data')
                t.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, t)
        commit = subprocess.run(['git', '-C', str(proj), 'rev-parse', '--short', 'HEAD'], capture_output=True, text=True, encoding='utf-8', errors='replace').stdout.strip()
        notes.append(f'코드 커밋 {commit}')
        r = subprocess.run([sys.executable, 'check_data.py'], cwd=proj, capture_output=True, text=True, encoding='utf-8', errors='replace', env=env)
        notes.append(f"check_data {'통과' if r.returncode == 0 else '실패'}")
        ok = ok and r.returncode == 0
        before = {p.name: sha1(p) for p in (proj / 'app' / 'data').glob('*.json')}
        r = subprocess.run([sys.executable, 'build_web_data.py'], cwd=proj, capture_output=True, text=True, encoding='utf-8', errors='replace', env=env)
        after = {p.name: sha1(p) for p in (proj / 'app' / 'data').glob('*.json')}
        same = r.returncode == 0 and before == after
        notes.append(f'앱 데이터 다시 만들기 {len(after)}개 ' + ('되살린 판과 같음' if same else '다름'))
        ok = ok and same
        rel = [f.relative_to(proj) for f in (proj / 'data').rglob('*') if f.is_file()]
        only = [x.as_posix() for x in rel if not (ROOT / x).exists()]
        diff = [x.as_posix() for x in rel if (ROOT / x).exists() and sha1(ROOT / x) != sha1(proj / x)]
        notes.append(f'참고: 지금 프로젝트와 내용 다름 {len(diff)}개(백업 뒤 바뀐 것)' + (f' 예 {diff[:3]}' if diff else '') +
                     f' · 백업에만 있음 {len(only)}개(프로젝트에서 지운 옛 파일 — 백업은 지우지 않는다)')
    finally:
        def unlock(func, path, _):                                  # git 객체는 읽기 전용이라 지우기 전에 풀어 준다
            os.chmod(path, 0o700); func(path)
        shutil.rmtree(tmp, onerror=unlock)
    print(f'복구 시험({day}): ' + ' · '.join(notes) + f" → {'통과' if ok else '실패'}")
    return ok


def main():
    if '--복구시험' in sys.argv:
        sys.exit(0 if restore_test() else 1)
    if not backup_repo():
        sys.exit(1)
    if '--no-cloud' not in sys.argv and not cloud_backup():
        sys.exit(1)
    if '--no-push' not in sys.argv and not push():
        sys.exit(1)


if __name__ == '__main__':
    main()
