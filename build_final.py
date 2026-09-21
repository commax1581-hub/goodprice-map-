"""검증 결과 통합 → 최종 마스터 생성
카카오 매칭 + 네이버 교차검증 + 전화번호 검증 + 도로명주소 검증
결과: data/processed/goodprice_final.csv / .json
"""
import pandas as pd

P = 'data/processed/'
d = pd.read_csv(P + 'match_status.csv', dtype=str).fillna('')
ph = pd.read_csv(P + 'phone_verify.csv', dtype=str).fillna('')
ad = pd.read_csv(P + 'address_check.csv', dtype=str).fillna('')

# ---- 전화번호 검증 반영(카카오 장소 확보분 포함) ----
ok = ph[ph.전화매칭.str.startswith('전화일치')].set_index('관리번호')
for gid, r in ok.iterrows():
    i = d.index[d.관리번호 == gid]
    d.loc[i, ['카카오장소ID', '카카오장소명', '카카오링크']] = [r.카카오장소ID, r.카카오장소명, r.카카오링크]
    d.loc[i, ['거리m', '최종상태', '전화검증']] = [r.거리m, '전화번호확인', r.전화매칭]
d['전화검증'] = d.get('전화검증', '').fillna('')
d.loc[d.관리번호.isin(ph[~ph.전화매칭.str.startswith('전화일치')].관리번호), '전화검증'] = \
    ph.set_index('관리번호').전화매칭.reindex(d.관리번호).values[d.관리번호.isin(ph[~ph.전화매칭.str.startswith('전화일치')].관리번호)]

# ---- 주소 검증 반영 ----
ad_i = ad.set_index('관리번호')
for col, src in [('주소검증', '검증결과'), ('정규주소', '정규주소'), ('우편번호', '우편번호'),
                 ('행정동', '행정동'), ('건물명', '건물명'), ('주소비고', '비고')]:
    d[col] = d.관리번호.map(ad_i[src]).fillna('')

# ---- 최종 등급 ----
def grade(r):
    if r.최종상태 in ('자동채택', '전화번호확인'):
        return '확정'
    if r.최종상태 == '네이버확인':
        return '확정(네이버)'
    return '검수필요'


d['데이터등급'] = d.apply(grade, axis=1)
d['검수사유'] = d.apply(lambda r: '; '.join(filter(None, [
    {'위치상이': '검색된 동명 업소가 멀리 있음', '없음': '카카오·네이버 모두 미검색(폐업 의심)',
     '상호상이': '같은 위치에 다른 상호'}.get(r.네이버판정, '') if r.데이터등급 == '검수필요' else '',
    '전화번호 불일치' if r.전화검증 == '불일치' else ('전화번호 없음' if r.전화검증 == '전화번호없음' else ''),
    '주소 미확인' if r.주소검증 == '주소없음' else '',
    r.주소비고 if r.주소비고.startswith('시군구') else ''])), axis=1)

d.to_csv(P + 'goodprice_final.csv', index=False, encoding='utf-8-sig')
d.to_json(P + 'goodprice_final.json', orient='records', force_ascii=False)

print('데이터등급', d.데이터등급.value_counts().to_dict())
print('카카오 장소ID 보유', (d.카카오장소ID != '').sum())
print('주소검증', d.주소검증.value_counts().to_dict())
print('검수 대상(등급 or 주소오류)', ((d.데이터등급 == '검수필요') | (d.주소검증 == '주소없음')).sum())
