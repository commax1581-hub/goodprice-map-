"""backup_data.py 실패 주입 시험 — 실제 백업 저장소·드라이브는 건드리지 않는다(임시 폴더·작은 시험 저장소). 실행: python test_backup_data.py"""
import os, shutil, subprocess, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import backup_data as B

ok_all = True
def check(name, cond):
    global ok_all
    ok_all &= bool(cond)
    print(('✓ ' if cond else '✗ ') + name)

# 1. 지금 원본은 모두 내용 검사 통과
files = B.source_files()
bad = [(f, r) for f in files for r in [B.content_problem(f)] if r]
check(f'원본 {len(files)}개 내용 검사 통과', not bad)
for f, r in bad[:5]: print('   ', f, r)

tmp = Path(tempfile.mkdtemp(prefix='bk_test_'))
try:
    # 깨진 json은 잡는가
    j = tmp / 'x.json'; j.write_text('{"a": 1', encoding='utf-8')
    check('잘린 json을 잡음', B.content_problem(j) is not None)

    # 2. 복사 도중 망가지면 정상본이 남는가
    src = next(f for f in files if f.suffix == '.json' and f.stat().st_size > 1000)
    dest = tmp / 'dest'
    n, fails = B.copy_files([src], dest)
    dst = dest / src.relative_to(B.ROOT)
    good = B.sha1(dst)
    os.utime(dst, (0, 0))                                   # 옛날 것으로 만들어 다시 복사하게
    real_copy = shutil.copy2
    def broken_copy(a, b):
        Path(b).write_bytes(Path(a).read_bytes()[:100])      # 반쯤 쓰다 끊긴 것처럼
    B.shutil.copy2 = broken_copy
    n, fails = B.copy_files([src], dest)
    B.shutil.copy2 = real_copy
    check('복사 실패를 알아챔', len(fails) == 1)
    check('정상본이 그대로', B.sha1(dst) == good)
    check('.part가 남지 않음', not list(dest.rglob('*.part')))

    # 3·4. 드라이브: 작은 시험 저장소 셋 + 임시 CLOUD
    repos = []
    for name in ('착한식당-data', '착한식당', '공통지식'):
        r = tmp / 'repos' / name; r.mkdir(parents=True)
        subprocess.run(['git', 'init', '-q', '-b', 'main'], cwd=r, check=True)
        (r / 'a.txt').write_text(name, encoding='utf-8')
        subprocess.run(['git', '-c', 'user.email=t@t', '-c', 'user.name=t', 'commit', '-q', '--allow-empty', '-m', 'x'], cwd=r, check=True)
        subprocess.run(['git', 'add', '--', 'a.txt'], cwd=r, check=True)
        subprocess.run(['git', '-c', 'user.email=t@t', '-c', 'user.name=t', 'commit', '-q', '-m', 'y'], cwd=r, check=True)
        repos.append((name, r))
    B.cloud_repos = lambda: repos
    B.CLOUD = tmp / 'G' / '내 드라이브' / '백업' / '착한식당'
    B.CLOUD.mkdir(parents=True)
    check('정상 실행 통과', B.cloud_backup())
    today = sorted(p for p in B.CLOUD.iterdir() if p.is_dir())[-1]
    for i in range(1, 6):                                    # 다 갖춰진 옛 날 5개 + 덜 된 날 1개
        old = B.CLOUD / f'2025-01-0{i}'; shutil.copytree(today, old)
    (B.CLOUD / '2025-02-01').mkdir()
    keep = B.sha1(today / '공통지식.bundle')
    real_run = subprocess.run
    def failing_run(cmd, *a, **k):
        if 'bundle' in cmd and 'create' in cmd and '공통지식' in str(cmd[-2]):
            return subprocess.CompletedProcess(cmd, 1, '', '시험용 실패')
        return real_run(cmd, *a, **k)
    B.subprocess.run = failing_run
    res = B.cloud_backup()
    B.subprocess.run = real_run
    check('bundle 실패를 알림', res is False)
    check('그날 있던 공통지식.bundle 정상본이 그대로', B.sha1(today / '공통지식.bundle') == keep)
    check('실패 때 오래된 벌을 지우지 않음', len(B.complete_days()) == 6)
    check('.bundle.part가 남지 않음', not list(B.CLOUD.rglob('*.part')))
    check('정상 실행 뒤 4벌로 정리', B.cloud_backup() and len(B.complete_days()) == 4)
    check('덜 된 날은 4벌 셈에 안 들어감', (B.CLOUD / '2025-02-01').exists() and '2025-02-01' not in B.complete_days())
finally:
    def unlock(func, path, _):
        os.chmod(path, 0o700); func(path)
    shutil.rmtree(tmp, onerror=unlock)

print('\n' + ('✅ 시험 통과' if ok_all else '❌ 시험 실패'))
sys.exit(0 if ok_all else 1)
