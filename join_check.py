import pandas as pd, json, re
R='data/raw/'
def nname(s):
    s=str(s or '')
    s=re.sub(r'㈜|\(주\)|주식회사','',s)
    return re.sub(r'[\s\W_]+','',s).lower()
def road(s):
    s=re.sub(r'\([^)]*\)','',str(s or ''))
    m=re.search(r'([가-힣A-Za-z0-9·.]+(?:로|길))\s*(\d+(?:-\d+)?)',s)
    return (m.group(1)+m.group(2)) if m else re.sub(r'\s+','',s)
x=pd.read_excel(R+'goodprice_excel_전국_2026-09-19.xls',header=2,dtype=str)
m=pd.DataFrame(json.load(open(R+'goodprice_map_2026-09-19.json',encoding='utf-8'))['items'])
c=pd.read_csv(R+'datagokr_goodprice.csv',dtype=str,encoding='cp949')
print('csv',c.shape, c['업종'].value_counts().to_dict())
for d,n,a in [(x,'업소명','주소'),(m,'bsshNm','roadNmAddr'),(c,'업소명','주소')]:
    d['k_name']=d[n].map(nname); d['k_road']=d[a].map(road); d['key']=d.k_name+'|'+d.k_road
for nm,d in [('excel',x),('map',m),('csv',c)]:
    print(nm,'dup keys',d.key.duplicated(keep=False).sum())
print('excel∩map', x.key.isin(m.key).sum(), '/', len(x))
print('csv∩map', c.key.isin(m.key).sum(), '/', len(c))
print('csv name-only ∩ map', c.k_name.isin(m.k_name).sum())
print(c[~c.key.isin(m.key)][['업소명','주소']].head(15).to_string())
print('----debug')
miss=c[~c.key.isin(m.key)]
for _,r in miss.head(12).iterrows():
    hit=m[m.k_name==r.k_name]
    print(r['업소명'],'|',r['주소'],'|',r.k_road,' => ', hit[['bsshNm','roadNmAddr','k_road']].values.tolist()[:2])
