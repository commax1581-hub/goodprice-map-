import os, win32com.client as w, pandas as pd
p=os.path.abspath('착한가격업소_코드화_검색_분석_2026-09-19.xlsx')
xl=w.DispatchEx('Excel.Application'); xl.Visible=False; xl.DisplayAlerts=False
try:
    wb=xl.Workbooks.Open(p)
    xl.CalculateFullRebuild()
    errs={}
    for sh in wb.Worksheets:
        v=sh.UsedRange.Value
        n=0; sample=[]
        for ri,row in enumerate(v or []):
            for ci,x in enumerate(row or []):
                if isinstance(x,int) and x < -2146820000:
                    n+=1
                    if len(sample)<5: sample.append((ri+1,ci+1,x))
        errs[sh.Name]=(n,sample)
    print('errors',errs)
    s=wb.Worksheets('검색'); a=wb.Worksheets('분석')
    print('검색 김밥 결과수', s.Range('C10').Value, '| 1행', s.Range('C13:I13').Value)
    print('분석 서울x한식', a.Range('B5').Value, '| 합계행', a.Range('N21').Value, '| 차이', a.Range('N22').Value)
    print('업종 가격 행', a.Range('A26:F27').Value)
    print('편의 서울', a.Range('A42:E42').Value)
    print('결합현황', a.Range('A61:C71').Value)
    wb.Save()
finally:
    try: wb.Close(False)
    except Exception: pass
    try: xl.Quit()
    except Exception: pass
m=pd.read_csv('data/processed/goodprice_master.csv',dtype=str).fillna('')
t=(m.업소명+' '+m.메뉴1+' '+m.메뉴2+' '+m.메뉴3+' '+m.메뉴4+' '+m.사이트대표메뉴)
print('PY 김밥', t.str.contains('김밥',case=False).sum(), '| PY 서울x한식', ((m.시도=='서울특별시')&(m.업종=='한식')).sum(), '| PY 전체', len(m))
