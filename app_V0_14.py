
import io, re, sqlite3, unicodedata, html, os
from datetime import datetime, date, time, timedelta
from calendar import monthrange
import pandas as pd
import streamlit as st

st.set_page_config(page_title="AGCO | Pareto QG09 V0.14", page_icon="📊", layout="wide")
APP_VERSION="V0.14"; DB="pareto_qg09_v014.db"; POSTO_FIXO="QG09"
LOGO_FILE="agco_logo.png"
MAPA_MODELOS={"VTBAGFC":"VTBA","V2MFGFC":"V2 MF","V2VTGFC":"V2 VT","G7GFCAN":"G7","G8GFCAN":"G8"}
ALIASES={"CD_POSTO_CN":["CD_POSTO_CN","CD_POSTO_FALHA","POSTO","POSTO_CN","CD_POSTO"],"CD_MODELO":["CD_MODELO","MODELO","COD_MODELO"],"DT_HR_INSPECAO":["DT_HR_INSPECAO","DT_CRIACAO_FALHA","DT_ENC_CERTIFICADO","DT_ENCERRAMENTO_FALHA","DATA_INSPECAO","DATA"],"ANOMALIA_FALHA":["ANOMALIA_FALHA","FALHA","ANOMALIA","DESCRICAO_FALHA"],"D1":["D1"],"NR_WO":["NR_WO","WO","ORDEM"],"NR_SERIE":["NR_SERIE","SERIE","CHASSI"],"POSTO_ORIGEM_FALHA":["POSTO_ORIGEM_FALHA","ORIGEM_FALHA","POSTO_ORIGEM","ORIGEM"],"C_AREA_ORIGEM_FALHA":["C_AREA_ORIGEM_FALHA","AREA_ORIGEM_FALHA","AREA_ORIGEM"],"C_DPU_QG_AMARELO":["C_DPU_QG_AMARELO","DPU","DPU_QG_AMARELO"]}
REQ=["CD_POSTO_CN","CD_MODELO","DT_HR_INSPECAO","ANOMALIA_FALHA"]; OPTIONAL=["D1","NR_WO","NR_SERIE","POSTO_ORIGEM_FALHA","C_AREA_ORIGEM_FALHA","C_DPU_QG_AMARELO"]
CSS="""
<style>
:root{--red:#C00031;--red2:#C41230;--black:#241F20;--bg:#101113;--panel:#181A1D;--panel2:#202327;--border:#3A3D42;--muted:#B7BDC6;--text:#F4F5F7;--white:#FFFFFF;}
.stApp{background:linear-gradient(180deg,#101113 0%,#17191C 100%);color:var(--text);} [data-testid="stSidebar"]{background:linear-gradient(180deg,#241F20 0%,#151315 100%);border-right:5px solid var(--red);} [data-testid="stSidebar"] *{color:#fff!important}.block-container{padding-top:1.0rem}.agco-header{display:flex;gap:20px;align-items:center;padding:22px 26px;border:1px solid var(--border);background:linear-gradient(135deg,#241F20 0%,#181A1D 62%,#3a0b16 100%);border-radius:12px;box-shadow:0 14px 34px rgba(0,0,0,.30);border-top:6px solid var(--red);margin-bottom:18px}.brand-word{font-size:2.15rem;font-weight:950;letter-spacing:.8px;color:#fff;border:2px solid #fff;padding:4px 12px;line-height:1}.brand-sub{font-size:.78rem;color:#fff;text-transform:uppercase;letter-spacing:1.4px;margin-top:4px}.head-title h1{margin:0;color:#fff;font-size:2.0rem}.head-title p{color:var(--muted);margin:6px 0 0}.badge{display:inline-block;padding:5px 10px;border-radius:4px;border:1px solid rgba(255,255,255,.18);background:rgba(192,0,49,.22);color:#fff;font-weight:800;font-size:.78rem;margin-right:6px;margin-top:8px;text-transform:uppercase}.panel{background:var(--panel);border:1px solid var(--border);border-left:5px solid var(--red);border-radius:10px;padding:18px;box-shadow:0 10px 24px rgba(0,0,0,.25);margin-bottom:16px}.kpi{background:linear-gradient(180deg,var(--panel2),var(--panel));border:1px solid var(--border);border-top:4px solid var(--red);border-radius:10px;padding:18px;min-height:115px}.kpi-label{color:var(--muted);font-size:.80rem;font-weight:900;text-transform:uppercase;letter-spacing:.6px}.kpi-value{color:#fff;font-size:1.55rem;font-weight:900;margin-top:8px}.kpi-sub{color:var(--muted);font-size:.85rem}.pareto-box{background:#fff;border:1px solid var(--border);border-radius:10px;padding:14px;overflow-x:auto}.small-note{color:#fff;background:var(--panel);border:1px solid var(--border);border-left:5px solid var(--red);padding:10px 12px;border-radius:8px;margin-bottom:12px}svg text{font-family:Arial,Helvetica,sans-serif}.stDataFrame{background:#fff!important}</style>
"""

def strip_accents(t): return ''.join(ch for ch in unicodedata.normalize('NFKD',str(t)) if not unicodedata.combining(ch))
def clean_col(c):
    t=strip_accents(str(c).replace('\\_','_').replace('\\','').strip()).upper(); t=re.sub(r'[^A-Z0-9]+','_',t); return re.sub(r'_+','_',t).strip('_')
def norm_cols(df):
    df=df.copy(); orig=list(df.columns); df.columns=[clean_col(c) for c in df.columns]; ex=set(df.columns); ren={}
    for can, als in ALIASES.items():
        if can in ex: continue
        for a in als:
            ca=clean_col(a)
            if ca in ex: ren[ca]=can; break
    if ren: df=df.rename(columns=ren)
    return df.loc[:,~df.columns.duplicated()].copy(), orig, list(df.columns)
def txt(v): return '' if pd.isna(v) else re.sub(r'\s+',' ',str(v).strip())
def posto(v):
    t=txt(v).upper(); return 'QG09' if 'QG09' in t else t
def modelo(v):
    c=txt(v).upper(); return MAPA_MODELOS.get(c,c or 'Não informado')
def d1geral(d1,anom):
    v=(txt(d1) or txt(anom)).upper(); v=re.sub(r'^(SOLDA|PE[CÇ]A|COMPONENTE)\s*[-–—]\s*','',v).strip(); v=re.sub(r'^SOLDA\s+','',v).strip(); return v or 'NÃO INFORMADO'
def parse_dt(s):
    dt=pd.to_datetime(s,errors='coerce'); m=dt.isna() & s.notna()
    if m.any(): dt.loc[m]=pd.to_datetime(s[m],errors='coerce',dayfirst=True)
    return dt
def read_file(up):
    ext=up.name.lower().split('.')[-1]; data=up.getvalue()
    if ext=='csv':
        last=None
        for enc in ['utf-16','utf-8-sig','latin1']:
            for sep in ['\t',';',',',None]:
                try: return norm_cols(pd.read_csv(io.BytesIO(data),encoding=enc,sep=sep,engine='python',dtype=str))
                except Exception as e: last=e
        raise ValueError(f'Não foi possível ler CSV: {last}')
    eng='openpyxl' if ext=='xlsx' else 'xlrd'; return norm_cols(pd.read_excel(io.BytesIO(data),engine=eng,dtype=str))
def prepare(raw):
    df=raw.copy(); miss=[c for c in REQ if c not in df.columns]
    if miss: raise ValueError('Colunas obrigatórias ausentes: '+', '.join(miss))
    for c in OPTIONAL:
        if c not in df.columns: df[c]=''
    df['CD_POSTO_CN']=df['CD_POSTO_CN'].map(posto); df['CD_MODELO']=df['CD_MODELO'].map(lambda x:txt(x).upper()); df['MODELO_CORRIGIDO']=df['CD_MODELO'].map(modelo); df['DT_HR_INSPECAO']=parse_dt(df['DT_HR_INSPECAO']); df['ANOMALIA_FALHA']=df['ANOMALIA_FALHA'].map(txt); df['D1']=df['D1'].map(txt); df['D1_GERAL']=df.apply(lambda r:d1geral(r['D1'],r['ANOMALIA_FALHA']),axis=1)
    for c in ['NR_WO','NR_SERIE','POSTO_ORIGEM_FALHA','C_AREA_ORIGEM_FALHA']: df[c]=df[c].map(txt)
    q=df[df.CD_POSTO_CN.eq(POSTO_FIXO)&df.DT_HR_INSPECAO.notna()].copy(); f=q[q.ANOMALIA_FALHA.ne('')].copy(); cols=['CD_POSTO_CN','NR_WO','NR_SERIE','CD_MODELO','MODELO_CORRIGIDO','DT_HR_INSPECAO','ANOMALIA_FALHA','D1','D1_GERAL','POSTO_ORIGEM_FALHA','C_AREA_ORIGEM_FALHA','C_DPU_QG_AMARELO']; return df,q[cols],f[cols]
def con(): return sqlite3.connect(DB,check_same_thread=False)
def init(c):
    c.execute('CREATE TABLE IF NOT EXISTS upload_log(id INTEGER PRIMARY KEY AUTOINCREMENT,file_name TEXT,uploaded_at TEXT,total_rows INTEGER,qg09_rows INTEGER,falhas_rows INTEGER,min_date TEXT,max_date TEXT,mode TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS falhas_qg09(id INTEGER PRIMARY KEY AUTOINCREMENT,upload_id INTEGER,nr_wo TEXT,nr_serie TEXT,cd_modelo TEXT,modelo_corrigido TEXT,dt_hr_inspecao TEXT,anomalia_falha TEXT,d1 TEXT,d1_geral TEXT,posto_origem_falha TEXT,c_area_origem_falha TEXT)'); c.commit()
def del_period(c,sdate,edate): c.execute('DELETE FROM falhas_qg09 WHERE datetime(dt_hr_inspecao) BETWEEN datetime(?) AND datetime(?)',(datetime.combine(sdate,time(0,0)).isoformat(sep=' '),datetime.combine(edate,time(23,59,59)).isoformat(sep=' '))); c.commit()
def del_year(c,y): c.execute("DELETE FROM falhas_qg09 WHERE strftime('%Y', dt_hr_inspecao)=?",(str(y),)); c.commit()
def save(c,name,full,qg09,falhas,mode):
    mind=falhas.DT_HR_INSPECAO.dt.date.min().isoformat() if not falhas.empty else None; maxd=falhas.DT_HR_INSPECAO.dt.date.max().isoformat() if not falhas.empty else None
    cur=c.execute('INSERT INTO upload_log(file_name,uploaded_at,total_rows,qg09_rows,falhas_rows,min_date,max_date,mode) VALUES(?,?,?,?,?,?,?,?)',(name,datetime.now().isoformat(timespec='seconds'),len(full),len(qg09),len(falhas),mind,maxd,mode)); uid=cur.lastrowid
    rows=[(uid,r.NR_WO,r.NR_SERIE,r.CD_MODELO,r.MODELO_CORRIGIDO,r.DT_HR_INSPECAO.isoformat(sep=' ',timespec='seconds'),r.ANOMALIA_FALHA,r.D1,r.D1_GERAL,r.POSTO_ORIGEM_FALHA,r.C_AREA_ORIGEM_FALHA) for _,r in falhas.iterrows()]
    c.executemany('INSERT INTO falhas_qg09(upload_id,nr_wo,nr_serie,cd_modelo,modelo_corrigido,dt_hr_inspecao,anomalia_falha,d1,d1_geral,posto_origem_falha,c_area_origem_falha) VALUES(?,?,?,?,?,?,?,?,?,?,?)',rows); c.commit()
def load(c):
    df=pd.read_sql_query('SELECT nr_wo NR_WO,nr_serie NR_SERIE,cd_modelo CD_MODELO,modelo_corrigido MODELO_CORRIGIDO,dt_hr_inspecao DT_HR_INSPECAO,anomalia_falha ANOMALIA_FALHA,d1 D1,d1_geral D1_GERAL,posto_origem_falha POSTO_ORIGEM_FALHA,c_area_origem_falha C_AREA_ORIGEM_FALHA FROM falhas_qg09',c)
    if df.empty: return df
    df.DT_HR_INSPECAO=pd.to_datetime(df.DT_HR_INSPECAO,errors='coerce'); df.D1=df.D1.fillna('').astype(str); df.D1_GERAL=df.apply(lambda r:txt(r.D1_GERAL) or d1geral(r.D1,r.ANOMALIA_FALHA),axis=1); return df.drop_duplicates(subset=['NR_WO','NR_SERIE','CD_MODELO','DT_HR_INSPECAO','ANOMALIA_FALHA','POSTO_ORIGEM_FALHA'],keep='last')
def hist(c): return pd.read_sql_query('SELECT * FROM upload_log ORDER BY id DESC',c)
def clear(c): c.execute('DELETE FROM falhas_qg09'); c.execute('DELETE FROM upload_log'); c.commit()
def fint(v): return f'{int(v):,}'.replace(',','.') if pd.notna(v) else '0'
def fpct(v): return f'{float(v)*100:.1f}%'.replace('.',',')
def pareto(df,col,n):
    if df.empty or col not in df: return pd.DataFrame(columns=['Item','Quantidade','Percentual','Percentual Acumulado'])
    s=df[col].fillna('').astype(str).str.strip(); s=s[s.ne('')]
    if s.empty: return pd.DataFrame(columns=['Item','Quantidade','Percentual','Percentual Acumulado'])
    o=s.value_counts().head(n).reset_index(); o.columns=['Item','Quantidade']; t=o.Quantidade.sum(); o['Percentual']=o.Quantidade/t if t else 0; o['Percentual Acumulado']=o.Percentual.cumsum(); return o
def kpi(l,v,s=''): return f"<div class='kpi'><div class='kpi-label'>{html.escape(str(l))}</div><div class='kpi-value'>{html.escape(str(v))}</div><div class='kpi-sub'>{html.escape(str(s))}</div></div>"
def svg_bar(p,title):
    if p.empty: return "<div class='pareto-box'>Sem dados.</div>"
    p=p.copy().reset_index(drop=True); w,h,ml,mr,mt,mb=1180,540,70,45,55,165; pw=w-ml-mr; ph=h-mt-mb; mx=max(p.Quantidade.max(),1); step=pw/max(len(p),1); bw=min(step*.68,72); parts=[f"<div class='pareto-box'><svg viewBox='0 0 {w} {h}' width='100%' height='{h}'>","<rect width='100%' height='100%' fill='#FFFFFF'/>",f"<text x='{ml}' y='32' fill='#241F20' font-size='22' font-weight='800'>{html.escape(title)}</text>"]; pts=[]
    for i,r in p.iterrows():
        x=ml+step*i+step/2; bh=(r.Quantidade/mx)*ph; y=mt+ph-bh; lab=str(r.Item); short=lab[:28]+('...' if len(lab)>28 else '')
        parts += [f"<rect x='{x-bw/2:.1f}' y='{y:.1f}' width='{bw:.1f}' height='{bh:.1f}' fill='#C00031' rx='3'><title>{html.escape(lab)} - {int(r.Quantidade)}</title></rect>",f"<text x='{x:.1f}' y='{max(y-7,45):.1f}' fill='#241F20' font-size='12' text-anchor='middle'>{int(r.Quantidade)}</text>",f"<text x='{x:.1f}' y='{mt+ph+26}' fill='#657080' font-size='11' text-anchor='end' transform='rotate(-35 {x:.1f} {mt+ph+26})'>{html.escape(short)}</text>"]
        if 'Percentual Acumulado' in p: pts.append((x,mt+ph-r['Percentual Acumulado']*ph))
    if pts: parts.append("<polyline points='"+' '.join(f'{x:.1f},{y:.1f}' for x,y in pts)+"' fill='none' stroke='#241F20' stroke-width='3'/>")
    parts.append('</svg></div>'); return ''.join(parts)
def period(df,year,mode):
    ydf=df[df.DT_HR_INSPECAO.dt.year.eq(year)].copy(); mn,mx=ydf.DT_HR_INSPECAO.dt.date.min(),ydf.DT_HR_INSPECAO.dt.date.max()
    if mode=='Diário': d=st.sidebar.date_input('Dia',value=mx,min_value=mn,max_value=mx,format='DD/MM/YYYY'); return ydf,d,d,d.strftime('%d/%m/%Y')
    if mode=='Mensal': months=sorted(ydf.DT_HR_INSPECAO.dt.month.unique()); labels=[f'{m:02d}/{year}' for m in months]; lab=st.sidebar.selectbox('Mês',labels,index=len(labels)-1); m=int(lab[:2]); return ydf,date(year,m,1),date(year,m,monthrange(year,m)[1]),lab
    if mode=='Semanal': dates=sorted(ydf.DT_HR_INSPECAO.dt.date.unique()); mons=sorted({d-timedelta(days=d.weekday()) for d in dates}); labels=[f"Semana {i+1:02d} - {m.strftime('%d/%m/%Y')} a {(m+timedelta(days=6)).strftime('%d/%m/%Y')}" for i,m in enumerate(mons)]; lab=st.sidebar.selectbox('Semana',labels,index=len(labels)-1); ix=labels.index(lab); return ydf,mons[ix],mons[ix]+timedelta(days=6),lab
    if mode=='Anual YTD': return ydf,date(year,1,1),mx,f"YTD {year} até {mx.strftime('%d/%m/%Y')}"
    p=st.sidebar.date_input('Período personalizado',value=(mn,mx),min_value=mn,max_value=mx,format='DD/MM/YYYY')
    if isinstance(p,tuple) and len(p)==2: return ydf,p[0],p[1],f"Personalizado {p[0].strftime('%d/%m/%Y')} a {p[1].strftime('%d/%m/%Y')}"
    return ydf,mn,mx,'Personalizado'

c=con(); init(c); st.markdown(CSS,unsafe_allow_html=True)
logo_html = f"<img src='{LOGO_FILE}' style='max-height:58px;max-width:180px;background:white;padding:6px;border-radius:4px'/>" if os.path.exists(LOGO_FILE) else "<div><div class='brand-word'>AGCO</div><div class='brand-sub'>Corporation</div></div>"
st.markdown(f"<div class='agco-header'>{logo_html}<div class='head-title'><h1>Pareto de Falhas QG09</h1><p>Versão {APP_VERSION}: gráfico Top 10 ordenado e visual corporativo inspirado na AGCO.</p><span class='badge'>D1_GERAL</span><span class='badge'>Top 10 ordenado</span><span class='badge'>AGCO style</span><span class='badge'>QG09 fixo</span></div></div>",unsafe_allow_html=True)
df_all=load(c); tabs=st.tabs(['Dashboard','Estratificar TOP','Pareto por Modelo','Upload','Histórico'])
with st.sidebar:
    top_n=st.slider('Top N',5,25,10)
    if not df_all.empty: years=sorted(df_all.DT_HR_INSPECAO.dt.year.dropna().astype(int).unique()); year=st.selectbox('Ano',years,index=len(years)-1); mode=st.radio('Modo calendário',['Diário','Semanal','Mensal','Anual YTD','Personalizado'])
    else: year=None; mode='Personalizado'
with tabs[3]:
    st.markdown("<div class='panel'><b>Upload</b><br>Use Somar ao calendário para manter mais de um ano.</div>",unsafe_allow_html=True); imode=st.radio('Modo de importação',['Somar ao calendário','Substituir período do arquivo','Reprocessar ano inteiro do arquivo'],horizontal=True); up=st.file_uploader('Base (.csv, .xlsx ou .xls)',type=['csv','xlsx','xls'])
    if up:
        try:
            raw,orig,final=read_file(up); full,qg09,falhas=prepare(raw); st.success(f'Arquivo lido: {up.name} | Linhas: {len(full)} | QG09: {len(qg09)} | Falhas QG09: {len(falhas)}')
            with st.expander('Diagnóstico de cabeçalhos'): st.write('Originais',orig); st.write('Normalizados',final)
            st.dataframe(falhas.head(200),use_container_width=True,hide_index=True)
            if st.button('Salvar no calendário',type='primary') and not falhas.empty:
                mn=falhas.DT_HR_INSPECAO.dt.date.min(); mx=falhas.DT_HR_INSPECAO.dt.date.max()
                if imode=='Substituir período do arquivo': del_period(c,mn,mx)
                if imode=='Reprocessar ano inteiro do arquivo':
                    for y in sorted(falhas.DT_HR_INSPECAO.dt.year.unique()): del_year(c,int(y))
                save(c,up.name,full,qg09,falhas,imode); st.rerun()
        except Exception as e: st.error(str(e))
df_all=load(c)
if df_all.empty or year is None:
    for i in [0,1,2]:
        with tabs[i]: st.info('Faça upload da base.')
else:
    ydf,start,end,label=period(df_all,year,mode); st.sidebar.divider(); modelos=sorted(df_all.MODELO_CORRIGIDO.dropna().unique()); origens=sorted(df_all.POSTO_ORIGEM_FALHA.dropna().unique()); areas=sorted(df_all.C_AREA_ORIGEM_FALHA.dropna().unique()); ms=st.sidebar.multiselect('Modelo',modelos); osel=st.sidebar.multiselect('Origem',origens); asel=st.sidebar.multiselect('Área',areas)
    filt=ydf[(ydf.DT_HR_INSPECAO>=datetime.combine(start,time(0,0)))&(ydf.DT_HR_INSPECAO<=datetime.combine(end,time(23,59,59)))].copy()
    if ms: filt=filt[filt.MODELO_CORRIGIDO.isin(ms)]
    if osel: filt=filt[filt.POSTO_ORIGEM_FALHA.isin(osel)]
    if asel: filt=filt[filt.C_AREA_ORIGEM_FALHA.isin(asel)]
    pg=pareto(filt,'D1_GERAL',top_n)
    with tabs[0]:
        st.markdown(f"<div class='small-note'>Posto: <b>QG09</b> | Recorte: <b>{label}</b> | Pareto por <b>D1_GERAL</b></div>",unsafe_allow_html=True); a,b,c1,d=st.columns(4); a.markdown(kpi('Falhas',fint(len(filt))),unsafe_allow_html=True); b.markdown(kpi('Top 1',pg.iloc[0].Item if not pg.empty else '-'),unsafe_allow_html=True); c1.markdown(kpi('Qtd Top 1',fint(pg.iloc[0].Quantidade if not pg.empty else 0)),unsafe_allow_html=True); d.markdown(kpi('Modelos',fint(filt.MODELO_CORRIGIDO.nunique())),unsafe_allow_html=True); st.markdown(svg_bar(pg,f'Pareto Falha Geral - {label}'),unsafe_allow_html=True); show=pg.copy(); show.insert(0,'TOP',range(1,len(show)+1)); show['Percentual']=show.Percentual.map(fpct); show['Percentual Acumulado']=show['Percentual Acumulado'].map(fpct); st.dataframe(show,use_container_width=True,hide_index=True)
    with tabs[1]:
        if pg.empty: st.info('Sem dados.')
        else:
            opts=[f'TOP {i+1} - {r.Item} ({r.Quantidade})' for i,r in pg.reset_index(drop=True).iterrows()]; lab=st.selectbox('Escolha o TOP para estratificar',opts); top=pg.iloc[opts.index(lab)].Item; df_top=filt[filt.D1_GERAL.eq(top)].copy(); st.subheader(lab); bm=pareto(df_top,'MODELO_CORRIGIDO',25); st.markdown('### Distribuição por modelo'); st.markdown(svg_bar(bm,'Distribuição por modelo'),unsafe_allow_html=True); st.dataframe(bm.rename(columns={'Item':'Modelo'}),use_container_width=True,hide_index=True); mod=st.selectbox('Escolha o modelo para ver as informações completas',['Todos']+sorted(df_top.MODELO_CORRIGIDO.dropna().unique())); dfm=df_top.copy() if mod=='Todos' else df_top[df_top.MODELO_CORRIGIDO.eq(mod)].copy(); st.markdown(f"### Ranking das falhas completas - {'Todos os modelos' if mod=='Todos' else mod}"); det=pareto(dfm,'ANOMALIA_FALHA',50).rename(columns={'Item':'Falha completa'})
            if not det.empty:
                det=det[['Falha completa','Quantidade','Percentual','Percentual Acumulado']].copy(); det.insert(0,'Ranking',range(1,len(det)+1)); det['Qtd']=det['Quantidade']; det['Descrição ranking']=det.apply(lambda r:f"{int(r.Ranking)} - {r['Falha completa']} (qtd-{int(r.Qtd)})",axis=1); det['Percentual']=det.Percentual.map(fpct); det['Percentual Acumulado']=det['Percentual Acumulado'].map(fpct)
            st.dataframe(det[['Ranking','Falha completa','Qtd','Percentual','Percentual Acumulado','Descrição ranking']] if not det.empty else det,use_container_width=True,hide_index=True)
            st.markdown('### Gráfico Top 10 - falhas completas')
            if not det.empty:
                g=det.head(10)[['Falha completa','Qtd']].rename(columns={'Falha completa':'Item','Qtd':'Quantidade'}).copy(); total=float(g['Quantidade'].sum()); g['Percentual']=g['Quantidade']/total if total>0 else 0; g['Percentual Acumulado']=g['Percentual'].cumsum(); st.markdown(svg_bar(g,'Top 10 falhas completas - ordenado por quantidade'),unsafe_allow_html=True)
            else: st.info('Sem dados para o gráfico Top 10.')
            if mod=='Todos' and not det.empty:
                fs=st.selectbox('Escolha uma falha completa para ver os modelos envolvidos',det['Falha completa'].tolist()); pm=pareto(dfm[dfm.ANOMALIA_FALHA.eq(fs)],'MODELO_CORRIGIDO',25); st.markdown(svg_bar(pm,'Modelos envolvidos na falha completa'),unsafe_allow_html=True); st.dataframe(pm.rename(columns={'Item':'Modelo'}),use_container_width=True,hide_index=True)
            cols=['DT_HR_INSPECAO','NR_WO','NR_SERIE','CD_MODELO','MODELO_CORRIGIDO','D1_GERAL','D1','ANOMALIA_FALHA','POSTO_ORIGEM_FALHA','C_AREA_ORIGEM_FALHA']; st.markdown('### Registros completos'); st.dataframe(dfm[[x for x in cols if x in dfm.columns]].sort_values(['ANOMALIA_FALHA','MODELO_CORRIGIDO','DT_HR_INSPECAO']),use_container_width=True,hide_index=True)
    with tabs[2]:
        st.markdown("<div class='panel'><b>Pareto por Modelo</b><br>Escolha um modelo e veja o Pareto de falha geral dentro dele.</div>",unsafe_allow_html=True); mp=sorted(filt.MODELO_CORRIGIDO.dropna().unique())
        if not mp: st.info('Sem modelos disponíveis no recorte atual.')
        else:
            m=st.selectbox('Modelo para Pareto',mp); dfmp=filt[filt.MODELO_CORRIGIDO.eq(m)].copy(); pm=pareto(dfmp,'D1_GERAL',top_n); x,y,z=st.columns(3); x.markdown(kpi('Modelo',m,'Selecionado'),unsafe_allow_html=True); y.markdown(kpi('Falhas',fint(len(dfmp)),'No recorte'),unsafe_allow_html=True); z.markdown(kpi('Tipos de falha',fint(dfmp.D1_GERAL.nunique()),'D1_GERAL'),unsafe_allow_html=True); st.markdown(svg_bar(pm,f'Pareto por Modelo - {m} - {label}'),unsafe_allow_html=True); ps=pm.copy(); ps.insert(0,'TOP',range(1,len(ps)+1)); ps['Percentual']=ps.Percentual.map(fpct); ps['Percentual Acumulado']=ps['Percentual Acumulado'].map(fpct); st.dataframe(ps,use_container_width=True,hide_index=True)
with tabs[4]:
    st.dataframe(hist(c),use_container_width=True,hide_index=True)
    if st.button('Limpar calendário inteiro'): clear(c); st.rerun()
