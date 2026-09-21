"""공식 소식(공지 제목·날짜)을 PC에서 받아 app/data/notices.json으로 저장.
공식 누리집이 클라우드(Cloudflare) 접속을 막아 배포 서버에서는 실시간 수집이 안 되므로,
배포 전(분기 업데이트 때 또는 새 공지가 있을 때) 이 파일을 갱신해 함께 올린다.
실행: python update_notices.py
"""
import json, time
from pathlib import Path
from server import fetch_notices, NOTICE_URL

items = fetch_notices()
if not items:
    raise SystemExit('공지를 읽지 못했습니다 — 공식 사이트 구조 변경 여부 확인')
out = Path(__file__).parent / 'app' / 'data' / 'notices.json'
json.dump({'fetched_at': time.time(), 'source': NOTICE_URL, 'items': items},
          open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(f'공식 소식 {len(items)}건 저장 → {out}')
for i in items: print(' ', i['date'], i['title'][:40])
