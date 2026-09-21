"""목록용 사진 축소본 미리 만들기 → app/thumbs/<관리번호>.webp
- 공식 서버 부담을 줄이기 위해 동시 3건까지만, 요청 시작 사이 간격을 둔다.
- 이미 만든 사진은 건너뛰고(원본 주소가 바뀐 경우만 다시 만듦), 중단돼도 다시 실행하면 이어서 진행.
- 개발 서버가 만들어 둔 캐시(data/thumbs/<sha1>.webp)가 있으면 재사용.
실행: python gen_thumbs.py
"""
import glob, hashlib, io, json, threading, time, urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from PIL import Image, ImageFile, ImageOps
ImageFile.LOAD_TRUNCATED_IMAGES = True   # 공식 서버 원본이 잘려 있어도 읽을 수 있는 부분까지 사용

ROOT = Path(__file__).parent
OUT = ROOT / 'app' / 'thumbs'; OUT.mkdir(parents=True, exist_ok=True)
DEV_CACHE = ROOT / 'data' / 'thumbs'
MANIFEST = ROOT / 'data' / 'processed' / 'thumbs_manifest.json'   # 관리번호 → 원본 사진 주소
FAILED = ROOT / 'data' / 'processed' / 'thumbs_failed.json'
W, GAP, WORKERS = 360, 0.4, 3   # 축소 폭, 요청 사이 최소 간격(초), 동시 요청 수(공식 서버 배려)
UA = {'User-Agent': 'Mozilla/5.0 (personal-study; goodprice map mashup)'}


def shrink(raw):
    im = ImageOps.exif_transpose(Image.open(io.BytesIO(raw))).convert('RGB')
    im.thumbnail((W, W * 2))
    buf = io.BytesIO(); im.save(buf, 'WEBP', quality=72)
    return buf.getvalue()


def main():
    items = [it for f in sorted(glob.glob(str(ROOT / 'app' / 'data' / '[0-9]*.json')))
             for it in json.load(open(f, encoding='utf-8')) if it.get('img')]
    man = json.load(open(MANIFEST, encoding='utf-8')) if MANIFEST.exists() else {}
    failed = {}
    todo = [it for it in items if not ((OUT / f"{it['i']}.webp").exists() and man.get(it['i']) == it['img'])]
    print(f'사진 {len(items):,}장 중 새로 만들 것 {len(todo):,}장')
    t0, lock, done = time.time(), threading.Lock(), [0]
    last = [0.0]

    def work(it):
        out = OUT / f"{it['i']}.webp"
        dev = DEV_CACHE / (hashlib.sha1(it['img'].encode()).hexdigest() + '.webp')
        try:
            if dev.exists():
                out.write_bytes(dev.read_bytes())
            else:
                with lock:                               # 요청 시작 간격 유지
                    wait = GAP - (time.time() - last[0])
                    if wait > 0: time.sleep(wait)
                    last[0] = time.time()
                with urllib.request.urlopen(urllib.request.Request(it['img'], headers=UA), timeout=30) as r:
                    out.write_bytes(shrink(r.read(15 * 1024 * 1024)))
            with lock: man[it['i']] = it['img']
        except Exception as e:
            with lock: failed[it['i']] = f'{type(e).__name__}: {e}'[:120]
        with lock:
            done[0] += 1; n = done[0]
            if n % 200 == 0 or n == len(todo):
                json.dump(man, open(MANIFEST, 'w', encoding='utf-8'), ensure_ascii=False)
                el = time.time() - t0
                print(f'{n:,}/{len(todo):,}  실패 {len(failed)}  경과 {el/60:.0f}분  남은 약 {el/n*(len(todo)-n)/60:.0f}분', flush=True)

    with ThreadPoolExecutor(WORKERS) as ex:
        list(ex.map(work, todo))
    # 데이터에서 빠진 업소의 축소본 정리
    keep = {it['i'] for it in items}
    for p in OUT.glob('*.webp'):
        if p.stem not in keep:
            p.unlink(); man.pop(p.stem, None)
    json.dump(man, open(MANIFEST, 'w', encoding='utf-8'), ensure_ascii=False)
    json.dump(failed, open(FAILED, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    size = sum(p.stat().st_size for p in OUT.glob('*.webp'))
    print(f'완료: {len(list(OUT.glob("*.webp"))):,}장, {size/1024/1024:.0f}MB, 실패 {len(failed)}장(다시 실행하면 재시도)')


if __name__ == '__main__':
    main()
