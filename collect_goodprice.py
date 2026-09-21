"""goodprice.go.kr 착한가격업소 좌표·ID 수집 (시도별 1회 요청, 요청 간 2초 대기)"""
import json, time, datetime, requests

BASE = 'https://www.goodprice.go.kr'
BBOX = {'swLat': 33, 'swLng': 124, 'neLat': 39, 'neLng': 132, 'level': 4}
KEEP = ['bsshSn', 'bsshNm', 'indutyCd', 'indutyNm', 'roadNmAddr', 'lat', 'lot',
        'menuNm', 'menuPc', 'fileCours1', 'thumnAtchFileOrginlNm1']

s = requests.Session()
s.headers['User-Agent'] = 'Mozilla/5.0 (personal-study; goodprice map mashup)'

sido = s.post(BASE + '/comm/sys/selectCommCodeList.json', data={'mastrCdId': 'COM02'}).json()['commCodeList']
rows = []
for c in sido:
    time.sleep(2)
    r = s.post(BASE + '/bssh/selectMapData.json', data={**BBOX, 'srchCtpvCd': c['codeId']}).json()
    assert r['mode'] == 'point', (c, r['mode'])
    for it in r['items']:
        row = {k: it.get(k, '') for k in KEEP}
        row['ctpvCd'], row['ctpvNm'] = c['codeId'], c['codeNm']
        rows.append(row)
    print(c['codeId'], c['codeNm'], len(r['items']), flush=True)

stamp = datetime.date.today().isoformat()
with open(f'data/raw/goodprice_map_{stamp}.json', 'w', encoding='utf-8') as f:
    json.dump({'collected_at': stamp, 'source': BASE, 'count': len(rows), 'items': rows}, f, ensure_ascii=False)
print('total', len(rows))
