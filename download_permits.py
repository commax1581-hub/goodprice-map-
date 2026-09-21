"""지방행정 인허가 데이터 8종 다운로드 (file.localdata.go.kr) — 작은 것부터 순차"""
import time
from pathlib import Path
import requests

OUT = Path('data/raw/permits'); OUT.mkdir(parents=True, exist_ok=True)
DATASETS = [  # (저장명, URL, 건수)
    ('관광숙박업', 'https://file.localdata.go.kr/file/tourist_accommodations/info', 3439),
    ('목욕장업', 'https://file.localdata.go.kr/file/public_baths/info', 17470),
    ('숙박업', 'https://file.localdata.go.kr/file/lodgings/info', 55998),
    ('이용업', 'https://file.localdata.go.kr/file/barber_shops/info', 63894),
    ('세탁업', 'https://file.localdata.go.kr/file/laundries/info', 66480),
    ('미용업', 'https://file.localdata.go.kr/file/beauty_salons/info', 411192),
    ('휴게음식점', 'https://file.localdata.go.kr/file/rest_cafes/info', 561397),
    ('일반음식점', 'https://file.localdata.go.kr/file/general_restaurants/info', 2129830),
]
s = requests.Session(); s.headers['User-Agent'] = 'Mozilla/5.0'
for name, url, cnt in DATASETS:
    dest = OUT / f'{name}.zip'
    if dest.exists() and dest.stat().st_size > 10000:
        print(f'{name}: 이미 있음 ({dest.stat().st_size/1024/1024:.1f}MB)'); continue
    t0 = time.time(); total = 0
    try:
        with s.get(url, stream=True, timeout=3600) as r:
            ct = r.headers.get('Content-Type', '')
            with open(dest, 'wb') as f:
                for chunk in r.iter_content(1 << 20):
                    f.write(chunk); total += len(chunk)
                    if total % (50 << 20) < (1 << 20):
                        print(f'  {name} {total/1024/1024:.0f}MB...', flush=True)
        print(f'{name}({cnt:,}건): {total/1024/1024:.1f}MB, {time.time()-t0:.0f}초, {ct}', flush=True)
    except Exception as e:
        print(f'{name}: 실패 {e}', flush=True)
