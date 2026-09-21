"""분기 갱신 변경 분류 — 지난 분기와 번호(관리번호)별로 비교해 기존·추가·제외와 바뀐 항목을 나누고 보고서를 만든다.

실행:
  python diff_update.py --snapshot 2026-09-20      지금 데이터를 비교 기준(스냅숏)으로 저장 (배포 직후마다)
  python diff_update.py                            가장 최근 스냅숏 ↔ 지금 데이터 비교 → 보고서
  python diff_update.py --prev DIR --cur DIR       폴더끼리 비교(리허설·시험용)
  python diff_update.py --apply-review DIR         확인 목록 결정 반영(제외+신규 짝 '이어받기' → 번호 이어받기, 주소 보정 저장, CSV에만 있는 업소 숨김)
  python diff_update.py --csv-only                 CSV에만 있는 업소 확인 목록만 만들기

비교 파일(스냅숏에 들어가는 것): goodprice_master.csv, goodprice_detail.json, address_check.csv, kakao_match.csv, sbiz_link.csv(있으면)
결과: data/processed/update_<날짜>/ report.html · changes.csv · review.csv · summary.json
      data/processed/rematch_ids.json  (match_kakao.py 등이 다시 매칭할 번호)

분류 규칙 (docs/공공데이터-파이프라인.md 8장):
  추가 = 지난 분기에 없던 번호 / 제외 = 이번에 없는 번호 / 기존 = 둘 다 있는 번호
  기존 업소의 항목: 업체명 · 주소(이전 = 건물관리번호가 바뀜, 같은 건물 층 이동·표기 차이는 변경 없음) ·
                    가격 · 메뉴 · 영업시간 · 전화 · 편의시설 · 사진
  업체명 변경: 공식 업소번호가 같으면 확정, 아니면 의심(확인 목록)
  제외 1곳 + 추가 1곳이 같은 건물·같은 전화면 '제외+신규 짝'(상호만 바꾼 같은 가게일 수 있음) → 확인 목록
"""
import argparse, ast, csv, html, json, math, re, shutil, sys
from datetime import date
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).parent
P = ROOT / 'data' / 'processed'
SNAP = P / 'snapshots'
FILES = {'master': P / 'goodprice_master.csv', 'detail': ROOT / 'data' / 'raw' / 'goodprice_detail.json',
         'address': P / 'address_check.csv', 'kakao': P / 'kakao_match.csv', 'sbiz': P / 'sbiz_link.csv'}
FAC = {'F01': '주차', 'F02': '포장', 'F03': '배달', 'F04': '예약', 'F05': '남녀화장실', 'F06': '단체',
       'F07': '와이파이', 'F08': '반려동물', 'F09': '유아시설', 'F10': '장애인시설', 'F11': '임산부우대',
       'F12': '지역화폐(지류)', 'F13': '지역화폐(모바일)', 'F14': '지역화폐(카드)'}
ITEMS = ['업체명', '주소(이전)', '주소(층 이동)', '가격', '메뉴', '영업시간', '전화', '편의시설', '사진']
NO_CHANGE_ITEMS = {'주소(층 이동)', '주소(표기)'}     # 기록만 하고 '변경 없음'으로 본다
DROP_LIMIT = 0.10                                     # 전체 건수 급감 기준

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')


def nname(s):
    s = re.sub(r'㈜|\(주\)|주식회사', '', str(s or ''))
    return re.sub(r'[\s\W_]+', '', s).lower()


def digits(s):
    return re.sub(r'\D', '', str(s or ''))


def won(v):
    try:
        return f'{int(float(v)):,}'
    except (TypeError, ValueError):
        return str(v or '')


def dist_m(a, b):
    try:
        la1, lo1, la2, lo2 = map(float, (a[0], a[1], b[0], b[1]))
    except (TypeError, ValueError):
        return None
    dx = (lo2 - lo1) * 111320 * math.cos(math.radians((la1 + la2) / 2)); dy = (la2 - la1) * 110540
    return (dx * dx + dy * dy) ** 0.5


def listval(v):
    if isinstance(v, list):
        return v
    try:
        return ast.literal_eval(v) if v else []
    except (ValueError, SyntaxError):
        return []


def load(files):
    """번호 → 비교용 레코드"""
    m = pd.read_csv(files['master'], dtype=str).fillna('')
    det = {}
    if files['detail'].exists():
        det = {d['bsshSn']: d for d in json.load(open(files['detail'], encoding='utf-8')) if not d.get('오류')}
    ad = pd.read_csv(files['address'], dtype=str).fillna('').set_index('관리번호') if files['address'].exists() else pd.DataFrame()
    import addr_util as A
    recs = {}
    for _, r in m.iterrows():
        gid, sn = r['관리번호'], r['사이트업소번호'].strip()
        d = det.get(sn, {})
        menus = {}
        for x in listval(d.get('메뉴')):
            if x.get('명'):
                menus[str(x['명']).strip()] = x.get('가격')
        if not menus:                                    # 상세가 없으면 원천 메뉴1~4
            for i in range(1, 5):
                if r.get(f'메뉴{i}'):
                    menus[r[f'메뉴{i}'].strip()] = r.get(f'가격{i}')
        a = ad.loc[gid] if gid in ad.index else {}
        recs[gid] = {
            '관리번호': gid, '업소명': r['업소명'], 'sn': sn if sn != 'nan' else '', '주소': r['주소'],
            '시도': r['시도'], '시군구': r['시군구'], '전화': r['전화번호'], '좌표': (r['위도'], r['경도']),
            '건물': a.get('건물관리번호', '') if len(a) else '', '주소검증': a.get('검증결과', '') if len(a) else '',
            '층': A.floor_of(r['주소']), '도로키': A.road_key(r['주소']),
            '편의': {c: r.get(c, 'N') for c in FAC}, '메뉴': menus,
            '영업시간': re.sub(r'\s+', ' ', str(d.get('영업시간') or '')).strip(),
            '사진': sorted(listval(d.get('사진'))) or ([r['사진URL']] if r.get('사진URL') else []),
            '상세있음': bool(d),
        }
    cols = list(m.columns)
    kakao = pd.read_csv(files['kakao'], dtype=str).fillna('') if files['kakao'].exists() else pd.DataFrame()
    sbiz = pd.read_csv(files['sbiz'], dtype=str).fillna('') if files['sbiz'].exists() else None
    return recs, cols, kakao, sbiz


def compare(o, n):
    """기존 업소 한 곳의 바뀐 항목 [(항목, 전, 후)]"""
    ch = []
    if nname(o['업소명']) != nname(n['업소명']):
        ch.append(('업체명', o['업소명'], n['업소명']))
    if o['건물'] and n['건물']:
        if o['건물'] != n['건물']:
            ch.append(('주소(이전)', o['주소'], n['주소']))
        elif o['층'] != n['층']:
            ch.append(('주소(층 이동)', o['주소'], n['주소']))
        elif o['주소'] != n['주소']:
            ch.append(('주소(표기)', o['주소'], n['주소']))
    elif o['주소'] != n['주소']:                          # 건물관리번호를 못 얻은 경우: 도로명+건물번호, 좌표로 판단
        d = dist_m(o['좌표'], n['좌표'])
        moved = (o['도로키'] and n['도로키'] and o['도로키'] != n['도로키']) or (d is not None and d > 100)
        ch.append(('주소(이전)' if moved else ('주소(층 이동)' if o['층'] != n['층'] else '주소(표기)'), o['주소'], n['주소']))
    om, nm = o['메뉴'], n['메뉴']
    for k in om.keys() & nm.keys():
        if won(om[k]) != won(nm[k]):
            ch.append(('가격', f'{k} {won(om[k])}원', f'{k} {won(nm[k])}원'))
    added, removed = sorted(nm.keys() - om.keys()), sorted(om.keys() - nm.keys())
    if added or removed:
        ch.append(('메뉴', ', '.join(removed) and '−' + ', '.join(removed), ', '.join(added) and '+' + ', '.join(added)))
    if o['상세있음'] and n['상세있음'] and o['영업시간'] != n['영업시간']:
        ch.append(('영업시간', o['영업시간'], n['영업시간']))
    if digits(o['전화']) != digits(n['전화']):
        ch.append(('전화', o['전화'], n['전화']))
    fd = [FAC[c] + ('+' if n['편의'][c] == 'Y' else '−') for c in FAC if o['편의'][c] != n['편의'][c]]
    if fd:
        ch.append(('편의시설', '', ' '.join(fd)))
    if o['상세있음'] and n['상세있음'] and o['사진'] != n['사진']:
        ch.append(('사진', f'{len(o["사진"])}장', f'{len(n["사진"])}장'))
    return ch


def csv_only(master_path, final_path):
    """공공데이터 CSV에만 있고 공식 사이트에 없는 업소 → 숨김 후보(사이트가 최신이므로 사이트 우선, 2026-09-22 사용자 결정)
    사이트에만 있는 업소와 같은 전화·같은 건물이면 같은 가게(중복·상호 변경) → 대체 번호로 연결.
    나머지는 플랫폼(카카오·네이버·상가정보·전화)에서 찾아지면 '지정 해제 추정', 못 찾으면 '폐업·영업종료 추정'."""
    import difflib
    import addr_util as A
    m = pd.read_csv(master_path, dtype=str).fillna('')
    f = pd.read_csv(final_path, dtype=str).fillna('').set_index('관리번호') if Path(final_path).exists() else pd.DataFrame()
    ex_path = ROOT / 'data' / 'exclude_ids.json'
    done = {e['id'] for e in json.load(open(ex_path, encoding='utf-8'))} if ex_path.exists() else set()   # 이미 숨긴 곳은 다시 올리지 않음
    co, so = m[(m['출처'] == '공공데이터만') & ~m['관리번호'].isin(done)].copy(), m[m['출처'] == '사이트만'].copy()
    for d in (co, so):
        d['t'] = d['전화번호'].map(digits); d['rk'] = d['주소'].map(A.road_key)

    def sim(a, b):
        a, b = nname(a), nname(b)
        if not a or not b:
            return 0.0
        r = difflib.SequenceMatcher(None, a, b).ratio()
        return max(0.85, r) if (a in b or b in a) else r

    out = []
    for _, r in co.iterrows():
        best = None
        for _, s in so.iterrows():
            tel, bld = len(r.t) >= 9 and r.t == s.t, bool(r.rk) and r.rk == s.rk
            if not (tel or bld):
                continue
            sc = sim(r['업소명'], s['업소명'])
            kind = '중복(표기 차이)' if sc >= 0.6 else ('상호 변경' if tel else '')
            if kind and (not best or (kind == '중복(표기 차이)' and best[0] != kind)):
                best = (kind, s['관리번호'], s['업소명'], ' · '.join(w for w, ok in (('같은 전화', tel), ('같은 건물', bld)) if ok))
        e = f.loc[r['관리번호']] if len(f) and r['관리번호'] in f.index else {}
        g = (lambda k: e.get(k, '') if len(e) else '')
        alive = g('카카오장소ID') != '' or g('네이버판정') == '확인됨' or g('상가판정') in ('확인됨', '유사확인') or g('전화검증').startswith('전화일치')
        if best:
            kind, rid, rname, why = best
            out.append({'유형': 'CSV에만 있음', '관리번호': r['관리번호'], '업소명': r['업소명'], '내용': f'{kind}: 사이트에 "{rname}"({rid})',
                        '근거': why, '추천': '숨김(대체 번호로 연결)', '결정': '숨김', '대체': rid, '사유': kind})
        else:
            reason = '지정 해제 추정(영업 중으로 보임)' if alive else ('폐업·영업종료 추정(플랫폼에서 못 찾음)' if len(e) else '확인 전(플랫폼 검증 결과 없음)')
            out.append({'유형': 'CSV에만 있음', '관리번호': r['관리번호'], '업소명': r['업소명'], '내용': '공식 사이트에 없음',
                        '근거': reason, '추천': '숨김', '결정': '숨김', '대체': '', '사유': reason})
    return out


def run(prev_files, cur_files, out_dir):
    prev, pcols, _, psb = load(prev_files)
    cur, ccols, kakao, csb = load(cur_files)
    keep, add, drop = cur.keys() & prev.keys(), sorted(cur.keys() - prev.keys()), sorted(prev.keys() - cur.keys())
    changes, cls, review = [], {}, []
    for gid in sorted(keep):
        o, n = prev[gid], cur[gid]
        ch = compare(o, n)
        for item, before, after in ch:
            changes.append({'관리번호': gid, '업소명': n['업소명'], '항목': item, '전': before, '후': after})
        items = {c[0] for c in ch}
        real = items - NO_CHANGE_ITEMS
        if '업체명' in items:
            sure = o['sn'] and o['sn'] == n['sn']
            cls[gid] = '업체명 변경' if sure else '업체명 변경 의심'
            if not sure:
                review.append({'유형': '업체명 변경 의심', '관리번호': gid, '업소명': n['업소명'],
                               '내용': f"{o['업소명']} → {n['업소명']}", '근거': '공식 업소번호 없음 · 같은 번호로 이어짐',
                               '추천': '같은 업소', '결정': '같은 업소'})
        elif '주소(이전)' in items:
            cls[gid] = '이전'
        elif real:
            cls[gid] = '세부정보 변경'
        else:
            cls[gid] = '변경 없음'
    for gid in add:
        cls[gid] = '추가'
    # 제외 1곳 + 추가 1곳이 같은 건물·같은 전화 → 상호만 바꾼 같은 가게일 수 있음
    by_bd, by_tel = {}, {}
    for gid in drop:
        o = prev[gid]
        if o['건물']: by_bd.setdefault(o['건물'], []).append(gid)
        if len(digits(o['전화'])) >= 9: by_tel.setdefault(digits(o['전화']), []).append(gid)
    for gid in add:
        n = cur[gid]
        cand = set(by_bd.get(n['건물'], []) if n['건물'] else []) | set(by_tel.get(digits(n['전화']), []) if len(digits(n['전화'])) >= 9 else [])
        for old in sorted(cand):
            o = prev[old]
            why = ' · '.join(w for w, ok in (('같은 건물', n['건물'] and n['건물'] == o['건물']),
                                              ('같은 전화', digits(n['전화']) and digits(n['전화']) == digits(o['전화']))) if ok)
            review.append({'유형': '제외+신규 짝', '관리번호': f'{old} → {gid}', '업소명': f"{o['업소명']} / {n['업소명']}",
                           '내용': '지난 분기 업소가 빠지고 같은 곳에 새 업소가 추가됨', '근거': why,
                           '추천': '이어받기', '결정': '이어받기'})
    for gid in add + [g for g, c in cls.items() if c == '이전']:
        if cur[gid]['주소검증'] in ('주소없음', '조회실패'):
            review.append({'유형': '주소 확인', '관리번호': gid, '업소명': cur[gid]['업소명'], '내용': cur[gid]['주소'],
                           '근거': f"도로명주소 {cur[gid]['주소검증']}", '추천': '주소 보정(수정주소 칸 입력) 또는 공식 오류 신고',
                           '결정': '보류'})
    if psb is not None and csb is not None:          # 상가정보: 지난 분기엔 연결됐는데 이번엔 없음 → 폐업 의심(판정 아님)
        strong = lambda d: set(d[d['강도'] == '강함']['관리번호']) if '강도' in d else set(d['관리번호'])
        was, now = strong(psb), set(csb['관리번호'])          # 지난 분기에 '강하게' 연결됐는데 이번엔 아예 없음
        for gid in sorted((was - now) & keep):
            review.append({'유형': '폐업 의심', '관리번호': gid, '업소명': cur[gid]['업소명'], '내용': '상가정보에서 사라짐',
                           '근거': '상가정보는 기준일 차이가 있어 판정에 쓰지 않음', '추천': '유지(공식 지정 기준)', '결정': '유지'})
    review += csv_only(cur_files['master'], cur_files['master'].with_name('goodprice_final.csv'))
    # 매칭 검사: 카카오 장소 ID 하나가 두 업소에 / 좌표와 장소가 200m 넘게
    # 최종 결과(goodprice_final.csv)로 본다 — 중간 결과(kakao_match.csv)의 중복은 verify_naver.py가 정리하므로 오탐
    fin = cur_files['master'].with_name('goodprice_final.csv')
    if fin.exists():
        kakao = pd.read_csv(fin, dtype=str).fillna('')
    ex_path = ROOT / 'data' / 'exclude_ids.json'
    hidden = {e['id'] for e in json.load(open(ex_path, encoding='utf-8'))} if ex_path.exists() else set()
    if len(kakao):
        k = kakao[(kakao['카카오장소ID'] != '') & ~kakao['관리번호'].isin(hidden)]
        for pid, g in k.groupby('카카오장소ID'):
            if len(g) > 1:
                review.append({'유형': '매칭 검사', '관리번호': ', '.join(g['관리번호']), '업소명': ', '.join(g['업소명']),
                               '내용': f'카카오 장소 {pid}가 {len(g)}곳에 연결', '근거': '장소 ID는 가게 단위', '추천': '이름이 덜 비슷한 쪽 다시 매칭', '결정': '다시 매칭'})
        far = k[pd.to_numeric(k['거리m'], errors='coerce') > 200]
        for _, r in far.iterrows():
            review.append({'유형': '매칭 검사', '관리번호': r['관리번호'], '업소명': r['업소명'], '내용': f"카카오 장소가 좌표에서 {r['거리m']}m",
                           '근거': '200m 초과', '추천': '다시 매칭', '결정': '다시 매칭'})

    counts = {c: sum(1 for v in cls.values() if v == c) for c in ['변경 없음', '세부정보 변경', '업체명 변경', '업체명 변경 의심', '이전', '추가']}
    item_counts = {i: len({c['관리번호'] for c in changes if c['항목'] == i}) for i in ITEMS + ['주소(표기)']}
    rematch = sorted(g for g, c in cls.items() if c in ('업체명 변경', '업체명 변경 의심', '이전', '추가'))
    rematch += [x['관리번호'] for x in review if x['결정'] == '다시 매칭' and ',' not in x['관리번호']]
    anomalies = []
    if len(cur) < len(prev) * (1 - DROP_LIMIT):
        anomalies.append(f'전체 건수 급감: {len(prev):,} → {len(cur):,}')
    if set(pcols) != set(ccols):
        anomalies.append(f'원본 항목 구성 변경: 추가 {sorted(set(ccols) - set(pcols))} / 빠짐 {sorted(set(pcols) - set(ccols))}')
    summary = {'prev': len(prev), 'cur': len(cur), 'keep': len(keep), 'add': len(add), 'drop': len(drop),
               'keep_changed': sum(1 for g in keep if cls[g] not in ('변경 없음',)), 'counts': counts, 'items': item_counts,
               'rematch': len(set(rematch)), 'review': len(review), 'anomalies': anomalies,
               'address': {k: int(v) for k, v in pd.Series([r['주소검증'] for r in cur.values()]).value_counts().items()},
               'sbiz': None if csb is None else {'linked': int(csb['관리번호'].nunique()), 'total': len(cur)}}
    out_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(changes, columns=['관리번호', '업소명', '항목', '전', '후']).to_csv(out_dir / 'changes.csv', index=False, encoding='utf-8-sig')
    pd.DataFrame(review, columns=['유형', '관리번호', '업소명', '내용', '근거', '추천', '결정', '대체', '사유']).fillna('').assign(수정주소='').to_csv(out_dir / 'review.csv', index=False, encoding='utf-8-sig')
    pd.DataFrame([{'관리번호': g, '분류': c} for g, c in sorted(cls.items())] + [{'관리번호': g, '분류': '제외'} for g in drop]).to_csv(out_dir / 'classes.csv', index=False, encoding='utf-8-sig')
    json.dump(summary, open(out_dir / 'summary.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    (out_dir / 'report.html').write_text(report_html(summary, changes, review, drop, prev), encoding='utf-8')
    return summary, sorted(set(rematch))


def report_html(s, changes, review, drop, prev):
    e = lambda x: html.escape(str(x))
    c = s['counts']
    rows = lambda items: ''.join('<tr>' + ''.join(f'<td>{e(v)}</td>' for v in it) + '</tr>' for it in items)
    samples = [(x['관리번호'], x['업소명'], x['항목'], x['전'], x['후']) for x in changes if x['항목'] not in NO_CHANGE_ITEMS][:40]
    anom = ''.join(f'<li class="bad">{e(a)}</li>' for a in s['anomalies']) or '<li>원본 이상 없음(항목 구성 같음 · 건수 급감 없음)</li>'
    item_rows = rows([(i, f"{s['items'].get(i, 0):,}") for i in ITEMS])
    sb = s['sbiz']
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>분기 갱신 변경 보고서</title><style>
body{{font-family:Pretendard,"Malgun Gothic",sans-serif;margin:24px auto;max-width:1040px;padding:0 16px;color:#16181D;background:#fff;line-height:1.5}}
table{{border-collapse:collapse;width:100%;font-size:13px;margin:6px 0 18px}}th,td{{border-bottom:1px solid #E3E7EE;padding:6px 8px;text-align:left;vertical-align:top}}
th{{background:#F5F7FA}}.k{{display:inline-block;border:1px solid #E3E7EE;border-radius:10px;padding:8px 12px;margin:0 6px 6px 0}}.k b{{display:block;font-size:20px}}
.bad{{color:#C5221F;font-weight:700}}h2{{font-size:17px;margin-top:26px}}</style></head><body>
<h1>분기 갱신 변경 보고서</h1><p>생성 {date.today()} · diff_update.py</p>
<h2>1. 기존·추가·제외 업소 수</h2>
<div><span class="k">지난 분기<b>{s['prev']:,}</b></span><span class="k">기존<b>{s['keep']:,}</b>변경 없음 {c['변경 없음']:,} · 변경 있음 {s['keep_changed']:,}</span>
<span class="k">추가<b>{s['add']:,}</b></span><span class="k">제외<b>{s['drop']:,}</b></span><span class="k">이번 분기<b>{s['cur']:,}</b></span></div>
<p>검산: {s['prev']:,} − {s['drop']:,} = {s['keep']:,} · {s['keep']:,} + {s['add']:,} = {s['cur']:,} {'✓' if s['prev'] - s['drop'] == s['keep'] and s['keep'] + s['add'] == s['cur'] else '✗'}</p>
<ul>{anom}</ul>
<p>기존 업소 분류: 세부정보 변경 {c['세부정보 변경']:,} · 업체명 변경 {c['업체명 변경']:,}(의심 {c['업체명 변경 의심']:,}) · 이전 {c['이전']:,}</p>
<h2>2. 기존 업소에서 바뀐 정보 — 항목별 업소 수</h2><table><tr><th>항목</th><th>업소 수</th></tr>{item_rows}
<tr><td>주소 표기만 다름(변경 없음)</td><td>{s['items'].get('주소(표기)', 0):,}</td></tr></table>
<table><tr><th>관리번호</th><th>업소</th><th>항목</th><th>전</th><th>후</th></tr>{rows(samples)}</table><p>전체: changes.csv</p>
<h2>3. 주소 정제</h2><table><tr><th>도로명주소 대조</th><th>업소</th></tr>{rows(sorted(s['address'].items()))}</table>
<h2>4. 상가정보 대사</h2><p>{'연결 ' + format(sb['linked'], ',') + ' / ' + format(sb['total'], ',') + '곳' if sb else '이번 분기 대사 전(sbiz_link.csv 없음)'}</p>
<h2>5. 확인 목록 ({len(review)}곳, 추천값이 기본 결정)</h2>
<table><tr><th>유형</th><th>관리번호</th><th>업소</th><th>내용</th><th>근거</th><th>추천</th></tr>{rows([(r['유형'], r['관리번호'], r['업소명'], r['내용'], r['근거'], r['추천']) for r in review])}</table>
<p>결정 바꾸기: review.csv의 '결정' 칸 수정(주소 보정은 '수정주소' 칸) → python diff_update.py --apply-review 이 폴더</p>
<h2>6. 다음 단계 — 다시 매칭</h2><p>카카오 재매칭·네이버 재검증 {s['rematch']:,}곳(업체명 변경·이전·추가·매칭 검사) · 나머지는 이전 결과 재사용 · 구글은 이름·주소 링크라 자동</p>
<p>제외 {s['drop']:,}곳 예: {e(', '.join(prev[g]['업소명'] for g in drop[:10]))}</p></body></html>"""


def snapshot(label):
    d = SNAP / label
    d.mkdir(parents=True, exist_ok=True)
    for k, f in FILES.items():
        if f.exists():
            shutil.copy2(f, d / f.name)
    rm = P / 'rematch_ids.json'                     # 이번 분기 재매칭은 끝났으므로 다음 실행에 영향 없게 치운다
    if rm.exists():
        rm.replace(d / rm.name)
    print('스냅숏 저장:', d.relative_to(ROOT), [p.name for p in d.iterdir()])


def files_in(d):
    d = Path(d)
    return {k: d / f.name for k, f in FILES.items()}


def apply_review(d):
    d = Path(d)
    rv = pd.read_csv(d / 'review.csv', dtype=str).fillna('')
    reg_path = P / 'id_registry.json'
    reg = json.load(open(reg_path, encoding='utf-8'))
    moved = 0
    for _, r in rv[(rv['유형'] == '제외+신규 짝') & (rv['결정'] == '이어받기')].iterrows():
        old, new = [x.strip() for x in r['관리번호'].split('→')]
        for k, v in list(reg.items()):
            if v == new:
                reg[k] = old; moved += 1
    json.dump(reg, open(reg_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    ov = rv[(rv['유형'] == '주소 확인') & (rv['수정주소'] != '')]
    if len(ov):
        path = ROOT / 'data' / 'address_overrides.csv'
        new_file = not path.exists()
        with open(path, 'a', encoding='utf-8-sig' if new_file else 'utf-8', newline='') as f:
            w = csv.writer(f)
            if new_file: w.writerow(['관리번호', '수정주소', '사유', '날짜'])
            for _, r in ov.iterrows():
                w.writerow([r['관리번호'], r['수정주소'], '분기 갱신 확인 목록', date.today().isoformat()])
    # CSV에만 있는 업소 '숨김' → 제외 목록(사유·대체 번호 기록). 대체 번호가 있으면 옛 번호로 들어온 저장·공유 링크를 그 업소로 연결
    ex_path = ROOT / 'data' / 'exclude_ids.json'
    ex = json.load(open(ex_path, encoding='utf-8')) if ex_path.exists() else []
    have = {e['id'] for e in ex}
    hide = rv[(rv['유형'] == 'CSV에만 있음') & (rv['결정'] == '숨김') & (~rv['관리번호'].isin(have))]
    for _, r in hide.iterrows():
        ex.append({'id': r['관리번호'], 'reason': f"공식 사이트 미조회 — {r['사유']}", 'date': date.today().isoformat(),
                   **({'replace': r['대체']} if r.get('대체') else {})})
    json.dump(ex, open(ex_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'번호 이어받기 키 {moved}개, 주소 보정 {len(ov)}건, 숨김 {len(hide)}곳(대체 연결 {int((hide["대체"] != "").sum())}) 저장')
    print('→ 번호 이어받기·주소 보정이 있으면 python build_master.py 부터, 숨김만이면 python build_web_data.py 부터 다시 실행')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--snapshot'); ap.add_argument('--prev'); ap.add_argument('--cur'); ap.add_argument('--apply-review')
    ap.add_argument('--out'); ap.add_argument('--csv-only', action='store_true')
    a = ap.parse_args()
    if a.snapshot:
        snapshot(a.snapshot); sys.exit(0)
    if a.apply_review:
        apply_review(a.apply_review); sys.exit(0)
    if a.csv_only:
        out = Path(a.out) if a.out else P / f'csv_only_{date.today()}'
        out.mkdir(parents=True, exist_ok=True)
        rv = pd.DataFrame(csv_only(FILES['master'], P / 'goodprice_final.csv'))
        rv.assign(수정주소='').to_csv(out / 'review.csv', index=False, encoding='utf-8-sig')
        print(f'CSV에만 있음 {len(rv)}곳:', rv['사유'].value_counts().to_dict(), '→', (out / 'review.csv').relative_to(ROOT)); sys.exit(0)
    prev_dir = Path(a.prev) if a.prev else max((p for p in SNAP.iterdir() if p.is_dir()), key=lambda p: p.name)
    cur_files = files_in(a.cur) if a.cur else FILES
    out = Path(a.out) if a.out else P / f'update_{date.today()}'
    s, rematch = run(files_in(prev_dir), cur_files, out)
    if not a.cur:                                   # 실제 갱신일 때만 다시 매칭 목록을 남긴다(시험 비교는 남기지 않음)
        json.dump({'kakao': rematch, 'naver': rematch, 'from': str(out.relative_to(ROOT))},
                  open(P / 'rematch_ids.json', 'w', encoding='utf-8'), ensure_ascii=False)
    print(f"비교 기준 {prev_dir.name} → 지난 {s['prev']:,} · 기존 {s['keep']:,}(변경 {s['keep_changed']:,}) · 추가 {s['add']:,} · 제외 {s['drop']:,} · 이번 {s['cur']:,}")
    print('항목별:', {k: v for k, v in s['items'].items() if v})
    print(f"다시 매칭 {s['rematch']:,} · 확인 목록 {s['review']:,}" + (' · 이상: ' + ' / '.join(s['anomalies']) if s['anomalies'] else ''))
    print('보고서:', (out / 'report.html').relative_to(ROOT))
