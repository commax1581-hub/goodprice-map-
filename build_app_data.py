"""앱용 최종 데이터 생성
- 상세(영업시간·전체메뉴·사진) 병합
- 업종 보정(사이트 세부업종 우선), 중복 제거
- 영업시간 파싱(오픈/마감/휴무요일), 가격 이상치 표시
- 로드뷰 등 링크 생성
결과: data/processed/app_data.json / app_data.csv
"""
import json, re
from urllib.parse import quote
import pandas as pd

P = 'data/processed/'
d = pd.read_csv(P + 'goodprice_final.csv', dtype=str).fillna('')
det = {x['bsshSn']: x for x in json.load(open('data/raw/goodprice_detail.json', encoding='utf-8'))}

# ---------- 1) 중복 제거 ----------
key = d.업소명.str.replace(r'\s', '', regex=True) + '|' + d.주소.str.replace(r'\s', '', regex=True)
dup = key.duplicated()
print('중복 제거', int(dup.sum()))
d = d[~dup].reset_index(drop=True)

# ---------- 2) 업종 보정 ----------
BIG = {'한식': '한식', '중식': '중식', '일식': '일식', '양식': '양식', '베이커리': '베이커리',
       '기타요식업': '기타요식업', '세탁업': '세탁업', '목욕업': '목욕업', '숙박업': '숙박업',
       '이용업': '이용업', '미용업': '미용업', '기타비요식업': '기타비요식업'}


def fix_upjong(r):
    sub = r.세부업종
    if not sub:
        return r.업종, ''
    big = sub.split('_')[0]
    return (BIG.get(big, r.업종), sub.split('_')[1] if '_' in sub else '')


d[['업종', '세부분류']] = d.apply(lambda r: pd.Series(fix_upjong(r)), axis=1)
print('업종 보정 후:', d.업종.value_counts().to_dict())

# ---------- 3) 상세 병합 ----------
WD = {'월': 0, '화': 1, '수': 2, '목': 3, '금': 4, '토': 5, '일': 6}
TIME_RE = re.compile(r'(\d{1,2})\s*(?::\s*(\d{2})|\s*시\s*(?:(\d{1,2})\s*분)?)?\s*[~\-–]\s*'
                     r'(?:(?:다음\s*날|익일|오전|오후|AM|PM)\s*)?(\d{1,2})\s*(?::\s*(\d{2})|\s*시\s*(?:(\d{1,2})\s*분)?)?')
CHECKIN_RE = re.compile(r'입실\s*(\d{1,2}):(\d{2})[\s\S]*?퇴실\s*(\d{1,2}):(\d{2})')


def parse_hours(txt):
    """자유 텍스트 → (오픈, 마감, 휴무요일리스트, 파싱성공)"""
    t = ' '.join((txt or '').split())
    if not t or t in ('-', ':', '--'):
        return '', '', [], False
    off = [WD[w] for w in re.findall(r'([월화수목금토일])\s*(?:요일)?\s*(?:[,·]?\s*[월화수목금토일]\s*(?:요일)?)?\s*(?:정기)?\s*휴', t)]
    for seg in re.findall(r'매주\s*([월화수목금토일][,·\s]*[월화수목금토일]?)\s*(?:요일)?\s*(?:정기)?\s*휴', t):
        off += [WD[c] for c in seg if c in WD]
    if '연중무휴' in t:
        off = []
    open_ = close = ''
    m = CHECKIN_RE.search(t)          # 숙박업: 입실/퇴실
    if m:
        open_, close = f'{int(m.group(1)):02d}:{m.group(2)}', f'{int(m.group(3)):02d}:{m.group(4)}'
        return open_, close, sorted(set(off)), True
    if '24시간' in t or re.search(r'00:00\s*[~\-]\s*(?:익일\s*)?00:00', t):
        return '00:00', '24:00', sorted(set(off)), True
    m = TIME_RE.search(t)
    if m:
        h1 = int(m.group(1)); m1 = m.group(2) or m.group(3) or '00'
        h2 = int(m.group(4)); m2 = m.group(5) or m.group(6) or '00'
        pre = t[:m.start()]
        if ('오후' in pre or 'PM' in pre.upper()) and h1 < 12:
            h1 += 12
        mid = t[m.start():m.end()]
        if ('오후' in mid or '다음' in mid or '익일' in mid) and h2 < 12:
            h2 += 12
        elif h2 < h1 and h2 < 12:      # 9~5 → 09:00~17:00
            h2 += 12
        open_ = f'{h1 % 24:02d}:{int(m1):02d}'
        close = f'{h2:02d}:{int(m2):02d}' if h2 <= 24 else f'{h2 % 24:02d}:{int(m2):02d}'
        return open_, close, sorted(set(off)), True
    return '', '', sorted(set(off)), False


def take(sn, f, default=''):
    x = det.get(str(sn))
    return x.get(f, default) if x else default


d['영업시간원문'] = d.사이트업소번호.map(lambda s: take(s, '영업시간'))
hp = d.영업시간원문.map(parse_hours)
d['오픈'] = hp.map(lambda x: x[0])
d['마감'] = hp.map(lambda x: x[1])
d['휴무요일'] = hp.map(lambda x: ','.join(map(str, x[2])))
d['영업시간해석'] = hp.map(lambda x: 'Y' if x[3] else 'N')
d['업소설명'] = d.사이트업소번호.map(lambda s: take(s, '업소설명')).replace('-', '')
d['담당부서'] = d.사이트업소번호.map(lambda s: take(s, '담당부서'))
d['담당연락처'] = d.사이트업소번호.map(lambda s: take(s, '담당연락처'))
d['사진목록'] = d.사이트업소번호.map(lambda s: take(s, '사진', []) or [])
d['사진수'] = d.사진목록.map(len)


def menus(sn):
    ms = take(sn, '메뉴', []) or []
    return [{'명': m['명'], '가격': m['가격'], '지정': m.get('지정') == 'Y'} for m in ms if m.get('명')]


d['메뉴목록'] = d.사이트업소번호.map(menus)
# 사이트 메뉴가 없으면 공공데이터 메뉴1~4 사용
for i, r in d[d.메뉴목록.map(len) == 0].iterrows():
    ms = [{'명': r[f'메뉴{k}'], '가격': int(float(r[f'가격{k}'])) if r[f'가격{k}'] else None, '지정': True}
          for k in range(1, 5) if r[f'메뉴{k}']]
    d.at[i, '메뉴목록'] = ms
d['메뉴수'] = d.메뉴목록.map(len)
d['대표메뉴'] = d.메뉴목록.map(lambda m: m[0]['명'] if m else '')
d['대표가격'] = d.메뉴목록.map(lambda m: m[0]['가격'] if m else None)
d['최저가격'] = d.메뉴목록.map(lambda m: min([x['가격'] for x in m if x['가격']], default=None))

# ---------- 4) 가격 이상치 표시 ----------
FOOD = {'한식', '중식', '일식', '양식', '베이커리', '기타요식업'}


def price_flag(r):
    p = r.최저가격
    if not p:
        return '가격없음'
    if r.업종 in FOOD:
        if p < 500:
            return '이상(너무 낮음)'
        if p > 50000:
            return '확인(고가)'
    else:
        if p == 0:
            return '이상(0원)'
        if p > 300000:
            return '회차권 등 장기이용'
    return ''


d['가격비고'] = d.apply(price_flag, axis=1)

# ---------- 5) 링크 ----------
def links(r):
    nm, sgg, addr, la, lo = r.업소명, r.시군구, r.주소, r.위도, r.경도
    q = quote(f'{nm} {sgg}')
    return pd.Series({
        '링크_공식': f'https://www.goodprice.go.kr/bssh/bsshInfo.do?bsshSn={r.사이트업소번호}' if r.사이트업소번호 else '',
        '링크_카카오': r.카카오링크 or f'https://map.kakao.com/link/map/{quote(nm.replace(",", " "))},{la},{lo}',
        '링크_카카오로드뷰': f'https://map.kakao.com/link/roadview/{la},{lo}',
        '링크_네이버': f'https://map.naver.com/p/search/{q}',
        '링크_구글': f'https://www.google.com/maps/search/?api=1&query={quote(nm + " " + addr)}',
        '링크_구글로드뷰': f'https://www.google.com/maps/@?api=1&map_action=pano&viewpoint={la},{lo}',
        '길찾기_카카오': f'https://map.kakao.com/link/to/{quote(nm.replace(",", " "))},{la},{lo}',
        '길찾기_티맵': f'tmap://route?goalname={q}&goalx={lo}&goaly={la}',
    })


d = pd.concat([d, d.apply(links, axis=1)], axis=1)

# ---------- 저장 ----------
APP = ['관리번호', '데이터등급', '시도', '시군구', '행정동', '업종', '세부분류', '업소명', '주소', '정규주소', '우편번호',
       '건물명', '전화번호', '위도', '경도', '대표메뉴', '대표가격', '최저가격', '가격비고', '메뉴수', '메뉴목록',
       '영업시간원문', '오픈', '마감', '휴무요일', '영업시간해석', '업소설명', '담당부서', '담당연락처',
       '사진URL', '사진목록', '사진수', '카카오장소ID', '사이트업소번호'] + \
      [c for c in d.columns if c.startswith('F') and len(c) == 3] + \
      [c for c in d.columns if c.startswith(('링크_', '길찾기_'))]
app = d[APP]
# 행정구역 코드(시군구코드·필터코드·법정동코드·건물관리번호) — 주소 정제 결과의 현재 이름 기준, 버그이력 #58
import region_codes
recs = app.to_dict('records')
print('행정구역 코드', dict(region_codes.attach(recs)))
app = pd.DataFrame(recs)
app.to_json(P + 'app_data.json', orient='records', force_ascii=False)
app.drop(columns=['메뉴목록', '사진목록']).to_csv(P + 'app_data.csv', index=False, encoding='utf-8-sig')

print()
print('최종', len(app))
print('영업시간 해석 성공', (app.영업시간해석 == 'Y').sum(), f'({(app.영업시간해석=="Y").mean()*100:.1f}%)')
print('휴무요일 확보', (app.휴무요일 != '').sum())
print('메뉴 평균', round(app.메뉴수.mean(), 2), '| 메뉴 5개 이상', (app.메뉴수 >= 5).sum())
print('가격비고', app.가격비고.value_counts().to_dict())
print('사진 보유', (app.사진수 > 0).sum(), '| 여러 장', (app.사진수 > 1).sum())
