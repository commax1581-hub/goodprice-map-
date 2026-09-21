"""앱용 경량 데이터 생성 — 시도별 분할, 필드 축약
결과: app/data/index.json, app/data/<코드>.json
"""
import json, re
from pathlib import Path
import pandas as pd

SRC = 'data/processed/app_data.json'
OUT = Path('app/data'); OUT.mkdir(parents=True, exist_ok=True)
SIDO = {'서울특별시': '11', '부산광역시': '26', '대구광역시': '27', '인천광역시': '28', '대전광역시': '30',
        '울산광역시': '31', '세종특별자치시': '36', '경기도': '41', '강원특별자치도': '51', '충청북도': '43',
        '전남광주통합특별시': '12', '충청남도': '44', '전북특별자치도': '52', '경상북도': '47',
        '경상남도': '48', '제주특별자치도': '50'}
FAC = [('F01', '주차'), ('F02', '포장'), ('F03', '배달'), ('F04', '예약'), ('F05', '남녀화장실'),
       ('F06', '단체가능'), ('F07', '와이파이'), ('F08', '반려동물'), ('F09', '유아시설'),
       ('F10', '장애인시설'), ('F11', '임산부우대'), ('F12', '지역화폐'), ('F13', '지역화폐'), ('F14', '지역화폐')]



def norm_sgg(sido, g, dong):
    """시군구 정리: 세종은 시군구가 없어 읍면동을 사용, 주소가 붙어 들어온 값(예: 서구둔산로206번길)은 시군구만 남김"""
    if sido == '세종특별자치시':
        return dong or '세종시'
    if re.search(r'(시|군|구)$', g):
        return g
    m = re.match(r'^(.+?(?:시|군|구))', g)
    return m.group(1) if m else g


def clean(s):
    """화면에 그대로 넣는 글자에서 HTML 태그 문자 제거(분기 업데이트 대비)"""
    return re.sub(r'[<>]', '', s) if isinstance(s, str) else s


TIME_RANGE = re.compile(r'(\d{1,2}):(\d{2})\s*[~\-∼～〜]\s*(?:익일|다음날)?\s*(\d{1,2}):(\d{2})')


def fix_hours(o, c, h):
    """오픈=마감으로 잘못 뽑힌 경우(자정 넘김 영업) 원문에서 다시 읽고, 못 읽으면 '미확인' 처리"""
    if not o or o != c:
        return o, c
    for m in TIME_RANGE.finditer(h or ''):
        a, b = f'{int(m[1]):02d}:{m[2]}', f'{int(m[3]):02d}:{m[4]}'
        if a != b and int(m[1]) < 24 and int(m[3]) <= 24:
            return a, b
    return '', ''


rows = json.load(open(SRC, encoding='utf-8'))
# 제외 목록: 공식 사이트에서 조회되지 않는 업소 등 (docs/운영절차.md 2장). 번호 대장에서는 지우지 않는다.
EXCLUDE = Path('data/exclude_ids.json')
ex_list = json.load(open(EXCLUDE, encoding='utf-8')) if EXCLUDE.exists() else []
excl = {e['id'] for e in ex_list}
# 대체 번호: 같은 가게가 다른 번호로 남아 있는 경우(중복·상호 변경) 옛 번호의 저장·공유 링크를 그 업소로 연결
alias = {e['id']: e['replace'] for e in ex_list if e.get('replace')}
rows = [r for r in rows if r['관리번호'] not in excl]
if excl: print(f'제외 목록 {len(excl)}곳 제외')
df = pd.DataFrame(rows)
df = df.fillna('')

out_index = []
for sido, code in SIDO.items():
    g = df[df.시도 == sido]
    if not len(g):
        continue
    items = []
    for r in g.itertuples(index=False):
        d = r._asdict()
        fac = sorted({label for key, label in FAC if d.get(key) == 'Y'})
        menus = [[clean(m['명']), m['가격'], 1 if m.get('지정') else 0] for m in (d['메뉴목록'] or [])]
        items.append({
            'i': d['관리번호'], 'n': clean(d['업소명']), 'g': norm_sgg(sido, d['시군구'], d['행정동']), 'e': d['행정동'],
            'u': d['업종'], 's': d['세부분류'], 'a': clean(d['주소']), 't': d['전화번호'],
            'y': round(float(d['위도']), 6), 'x': round(float(d['경도']), 6),
            'm': menus, 'p': int(d['최저가격']) if d['최저가격'] else None,
            'h': clean(d['영업시간원문']) if d['영업시간원문'] not in ('-', ':', '--') else '',
            **dict(zip(('o', 'c'), fix_hours(d['오픈'], d['마감'], d['영업시간원문']))), 'w': d['휴무요일'],
            'f': fac, 'img': d['사진URL'],            # 사진목록·우편번호·데이터등급은 앱에서 안 써서 제외(용량 약 25%↓)
            'sn': d['사이트업소번호'], 'k': d['카카오장소ID'],
            'dept': clean(d['담당부서']), 'dtel': d['담당연락처'], 'bd': clean(d['건물명']),
        })
    items.sort(key=lambda v: (v['g'], v['n']))
    path = OUT / f'{code}.json'
    json.dump(items, open(path, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    sggs = sorted({v['g'] for v in items})
    out_index.append({'code': code, 'name': sido, 'count': len(items), 'sgg': sggs,
                      'size': round(path.stat().st_size / 1024 / 1024, 2)})
    print(f'{sido:12s} {len(items):5,}건  {path.stat().st_size/1024/1024:5.2f}MB')

meta = {'updated': '2026-09-20',
        'source': '공공데이터포털 행정안전부_착한가격업소 현황 + goodprice.go.kr',
        'total': int(len(df)), 'sido': out_index,
        'alias': {k: v for k, v in alias.items() if v in set(df.관리번호)},
        'upjong': df.업종.value_counts().to_dict(),
        'sub': {k: int(v) for k, v in df[df.세부분류 != ''].세부분류.value_counts().items()}}
json.dump(meta, open(OUT / 'index.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('\n총', len(df), '건 / 합계',
      round(sum(s['size'] for s in out_index), 1), 'MB')
