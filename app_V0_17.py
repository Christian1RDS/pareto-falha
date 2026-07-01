
import io, os, re, base64, sqlite3, unicodedata, html
from datetime import datetime, date, time, timedelta
from calendar import monthrange
import pandas as pd
import streamlit as st

st.set_page_config(page_title="AGCO | Pareto QG09 V0.17", page_icon="📊", layout="wide")
APP_VERSION = "V0.17"
DB = "pareto_qg09_v017.db"
POSTO_FIXO = "QG09"
LOGO_CANDIDATES = ["agco_logo.png","AGCO_logo.png","agco-logo.png","logo_agco.png","logo.png","AGCO.png","agco.png","agco_corporate_logo.png","AGCO_Corporate_Logo.png"]
MAPA_MODELOS = {"VTBAGFC":"VTBA", "V2MFGFC":"V2 MF", "V2VTGFC":"V2 VT", "G7GFCAN":"G7", "G8GFCAN":"G8"}
ALIASES = {
    "CD_POSTO_CN":["CD_POSTO_CN","CD_POSTO_FALHA","POSTO","POSTO_CN","CD_POSTO"],
    "CD_MODELO":["CD_MODELO","MODELO","COD_MODELO"],
    "DT_HR_INSPECAO":["DT_HR_INSPECAO","DT_CRIACAO_FALHA","DT_ENC_CERTIFICADO","DT_ENCERRAMENTO_FALHA","DATA_INSPECAO","DATA"],
    "ANOMALIA_FALHA":["ANOMALIA_FALHA","FALHA","ANOMALIA","DESCRICAO_FALHA"],
    "D1":["D1"], "NR_WO":["NR_WO","WO","ORDEM"], "NR_SERIE":["NR_SERIE","SERIE","CHASSI"],
    "POSTO_ORIGEM_FALHA":["POSTO_ORIGEM_FALHA","ORIGEM_FALHA","POSTO_ORIGEM","ORIGEM"],
    "C_AREA_ORIGEM_FALHA":["C_AREA_ORIGEM_FALHA","AREA_ORIGEM_FALHA","AREA_ORIGEM"],
    "C_DPU_QG_AMARELO":["C_DPU_QG_AMARELO","DPU","DPU_QG_AMARELO"],
}
REQ = ["CD_POSTO_CN","CD_MODELO","DT_HR_INSPECAO","ANOMALIA_FALHA"]
OPTIONAL = ["D1","NR_WO","NR_SERIE","POSTO_ORIGEM_FALHA","C_AREA_ORIGEM_FALHA","C_DPU_QG_AMARELO"]

CSS = """
<style>
:root{--red:#C00031;--black:#241F20;--bg:#101113;--panel:#181A1D;--panel2:#202327;--border:#3A3D42;--muted:#B7BDC6;--text:#F4F5F7;}
.stApp{background:linear-gradient(180deg,#101113 0%,#17191C 100%);color:var(--text);} 
[data-testid="stSidebar"]{background:linear-gradient(180deg,#241F20 0%,#151315 100%);border-right:5px solid var(--red);} 
[data-testid="stSidebar"] *{color:#fff!important}.block-container{padding-top:1rem;}
.agco-header{display:flex;gap:20px;align-items:center;padding:22px 26px;border:1px solid var(--border);background:linear-gradient(135deg,#241F20 0%,#181A1D 62%,#3a0b16 100%);border-radius:12px;box-shadow:0 14px 34px rgba(0,0,0,.30);border-top:6px solid var(--red);margin-bottom:18px;}
.logo-box{background:#fff;padding:8px 12px;border-radius:4px;display:flex;align-items:center;justify-content:center;min-width:145px;min-height:58px;}.brand-word{font-size:2.15rem;font-weight:950;color:#241F20}.brand-sub{font-size:.72rem;color:#241F20;text-transform:uppercase;letter-spacing:1.4px}.head-title h1{margin:0;color:#fff;font-size:2rem}.head-title p{color:var(--muted);margin:6px 0 0}.badge{display:inline-block;padding:5px 10px;border-radius:4px;border:1px solid rgba(255,255,255,.18);background:rgba(192,0,49,.22);color:#fff;font-weight:800;font-size:.78rem;margin-right:6px;margin-top:8px;text-transform:uppercase}.panel{background:var(--panel);border:1px solid var(--border);border-left:5px solid var(--red);border-radius:10px;padding:18px;box-shadow:0 10px 24px rgba(0,0,0,.25);margin-bottom:16px}.kpi{background:linear-gradient(180deg,var(--panel2),var(--panel));border:1px solid var(--border);border-top:4px solid var(--red);border-radius:10px;padding:18px;min-height:112px}.kpi-label{color:var(--muted);font-size:.80rem;font-weight:900;text-transform:uppercase}.kpi-value{color:#fff;font-size:1.55rem;font-weight:900;margin-top:8px}.kpi-sub{color:var(--muted);font-size:.85rem}.pareto-box{background:#fff;border:1px solid var(--border);border-radius:10px;padding:14px;overflow-x:auto}.small-note{color:#fff;background:var(--panel);border:1px solid var(--border);border-left:5px solid var(--red);padding:10px 12px;border-radius:8px;margin-bottom:12px}svg text{font-family:Arial,Helvetica,sans-serif}.stDataFrame{background:#fff!important}
</style>
"""

def logo_html():
    for logo_file in LOGO_CANDIDATES:
        if os.path.exists(logo_file):
            ext = os.path.splitext(logo_file)[1].lower().replace(".", "")
            mime = "jpeg" if ext in ["jpg", "jpeg"] else "png"
            with open(logo_file, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("utf-8")
            return f"<div class='logo-box'><img src='data:image/{mime};base64,{b64}' style='max-height:58px;max-width:180px;object-fit:contain;'/></div>"
    return "<div class='logo-box'><div><div class='brand-word'>AGCO</div><div class='brand-sub'>Corporation</div></div></div>"

def strip_accents(t): return ''.join(ch for ch in unicodedata.normalize('NFKD',str(t)) if not unicodedata.combining(ch))
def clean_col(c):
    t=strip_accents(str(c).replace('\\_','_').replace('\\','').strip()).upper(); t=re.sub(r'[^A-Z0-9]+','_',t); return re.sub(r'_+','_',t).strip('_')
def norm_cols(df):
    df=df.copy(); orig=list(df.columns); df.columns=[clean_col(c) for c in df.columns]; existing=set(df.columns); ren={}
    for can, als in ALIASES.items():
        if can in existing: continue
        for a in als:
            ca=clean_col(a)
            if ca in existing: ren[ca]=can; break
    if ren: df=df.rename(columns=ren)
    return df.loc[:,~df.columns.duplicated()].copy(), orig, list(df.columns)
def txt(v): return '' if pd.isna(v) else re.sub(r'\s+',' ',str(v).strip())
def posto(v):
    t=txt(v).upper(); return 'QG09' if 'QG09' in t else t
def modelo(v):
    c=txt(v).upper(); return MAPA_MODELOS.get(c,c or 'Não informado')
def d1geral(d1,anom):
    v=(txt(d1) or txt(anom)).upper(); v=re.sub(r'^(SOLDA|PE[CÇ]A|COMPONENTE)\s*[-–—]\s*','',v).strip(); v=re.sub(r'^SOLDA\s+','',v).strip(); return v or 'NÃO INFORMADO'
def extrai_regiao(anomalia):
    a = strip_accents(txt(anomalia)).upper()
    checks = [
        ('FECHAMENTO SUPERIOR','FECHAMENTO SUPERIOR'),('ESTR. TRASEIRA','ESTRUTURA TRASEIRA'),('ESTR TRASEIRA','ESTRUTURA TRASEIRA'),('ESTR. PARALAMAS','ESTRUTURA PARALAMAS'),('ESTR PARALAMAS','ESTRUTURA PARALAMAS'),
        ('LATERAL ESQUERDA','LATERAL ESQUERDA'),('LAT ESQ','LATERAL ESQUERDA'),('LATERAL ESQURDA','LATERAL ESQUERDA'),('LATERAL DIREITA','LATERAL DIREITA'),('LAT DIR','LATERAL DIREITA'),
        ('ASSOALHO','ASSOALHO'),('PISO','ASSOALHO/PISO'),('TETO','TETO'),('SUPERIOR','SUPERIOR'),('TRASEIRA','TRASEIRA'),('FRONTAL','FRONTAL'),('FRENTE','FRONTAL'),('INFERIOR','INFERIOR'),('PARALAMAS','PARALAMAS')]
    for key,val in checks:
        if key in a: return val
    return 'NÃO CLASSIFICADO'
def familia_defeito(d1, anomalia):
    d = strip_accents((txt(d1) or txt(anomalia))).upper()
    if any(x in d for x in ['RESPING','CORDAO','FALTA CORDAO','POROSIDADE','FUSAO','PENETRACAO','DEPOSICAO','SOLDA']): return 'SOLDA'
    if any(x in d for x in ['ACABAMENTO','OXIDADO','PINTURA']): return 'ACABAMENTO / SUPERFÍCIE'
    if any(x in d for x in ['FALTA COMPONENTE','PECA ERRADA','COMPONENTE FORA','FALTA MONTAR','NAO CHAMA']): return 'COMPONENTE / MONTAGEM'
    if any(x in d for x in ['DESALINHADO','TORTO','TORCIDO','CURTO','TENSIONADO','FORA DE POSICAO']): return 'DIMENSIONAL / POSIÇÃO'
    if any(x in d for x in ['DANIFICADO','QUEBRADO','CORTADO','TRINCADO']): return 'DANO'
    return 'OUTROS'
def parse_dt(s):
    dt=pd.to_datetime(s,errors='coerce'); m=dt.isna() & s.notna()
    if m.any(): dt.loc[m]=pd.to_datetime(s[m],errors='coerce',dayfirst=True)
    return dt
def enriquecer(df):
    if df.empty: return df
    df=df.copy()
    df['REGIAO_EXTRAIDA']=df['ANOMALIA_FALHA'].map(extrai_regiao)
    df['FAMILIA_DEFEITO']=df.apply(lambda r: familia_defeito(r.get('D1',''), r.get('ANOMALIA_FALHA','')), axis=1)
    df['SEMANA_INICIO']=df['DT_HR_INSPECAO'].dt.to_period('W-MON').apply(lambda r: r.start_time.date() if pd.notna(r.start_time) else None)
    return df

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
    q=df[df.CD_POSTO_CN.eq(POSTO_FIXO)&df.DT_HR_INSPECAO.notna()].copy(); f=q[q.ANOMALIA_FALHA.ne('')].copy()
    cols=['CD_POSTO_CN','NR_WO','NR_SERIE','CD_MODELO','MODELO_CORRIGIDO','DT_HR_INSPECAO','ANOMALIA_FALHA','D1','D1_GERAL','POSTO_ORIGEM_FALHA','C_AREA_ORIGEM_FALHA','C_DPU_QG_AMARELO']
    return df,enriquecer(q[cols]),enriquecer(f[cols])
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
    df.DT_HR_INSPECAO=pd.to_datetime(df.DT_HR_INSPECAO,errors='coerce'); df.D1=df.D1.fillna('').astype(str); df.D1_GERAL=df.apply(lambda r:txt(r.D1_GERAL) or d1geral(r.D1,r.ANOMALIA_FALHA),axis=1)
    return enriquecer(df.drop_duplicates(subset=['NR_WO','NR_SERIE','CD_MODELO','DT_HR_INSPECAO','ANOMALIA_FALHA','POSTO_ORIGEM_FALHA'],keep='last'))
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
def pareto_svg(p,title):
    if p.empty: return "<div class='pareto-box'>Sem dados.</div>"
    p=p.copy().reset_index(drop=True); w,h,ml,mr,mt,mb=1220,600,80,90,62,175; pw=w-ml-mr; ph=h-mt-mb; mx=max(float(p.Quantidade.max()),1.0); step=pw/max(len(p),1); bw=min(step*.68,74)
    def yq(q): return mt+ph-(float(q)/mx)*ph
    def yp(pc): return mt+ph-float(pc)*ph
    parts=[f"<div class='pareto-box'><svg viewBox='0 0 {w} {h}' width='100%' height='{h}'>","<rect width='100%' height='100%' fill='#FFFFFF'/>",f"<text x='{ml}' y='35' fill='#241F20' font-size='22' font-weight='800'>{html.escape(title)}</text>"]
    for k in range(6):
        q=mx*k/5; y=yq(q); pct=k/5
        parts += [f"<line x1='{ml}' y1='{y:.1f}' x2='{w-mr}' y2='{y:.1f}' stroke='#E2E5E9'/>",f"<text x='{ml-12}' y='{y+4:.1f}' fill='#657080' font-size='12' text-anchor='end'>{int(round(q))}</text>",f"<text x='{w-mr+12}' y='{yp(pct)+4:.1f}' fill='#657080' font-size='12'>{int(pct*100)}%</text>"]
    y80=yp(.8); parts += [f"<line x1='{ml}' y1='{y80:.1f}' x2='{w-mr}' y2='{y80:.1f}' stroke='#C00031' stroke-width='2.5' stroke-dasharray='8 7'/>",f"<text x='{w-mr-6}' y='{y80-8:.1f}' fill='#C00031' font-size='14' font-weight='800' text-anchor='end'>80%</text>"]
    pts=[]
    for i,r in p.iterrows():
        x=ml+step*i+step/2; bh=(r.Quantidade/mx)*ph; y=mt+ph-bh; lab=str(r.Item); short=lab[:28]+('...' if len(lab)>28 else '')
        parts += [f"<rect x='{x-bw/2:.1f}' y='{y:.1f}' width='{bw:.1f}' height='{bh:.1f}' fill='#C00031' rx='3'><title>{html.escape(lab)} - {int(r.Quantidade)}</title></rect>",f"<text x='{x:.1f}' y='{max(y-7,48):.1f}' fill='#241F20' font-size='12' font-weight='700' text-anchor='middle'>{int(r.Quantidade)}</text>",f"<text x='{x:.1f}' y='{mt+ph+26}' fill='#657080' font-size='11' text-anchor='end' transform='rotate(-35 {x:.1f} {mt+ph+26})'>{html.escape(short)}</text>"]
        pts.append((x,yp(r['Percentual Acumulado']),r['Percentual Acumulado']))
    parts.append("<polyline points='"+' '.join(f'{x:.1f},{y:.1f}' for x,y,_ in pts)+"' fill='none' stroke='#241F20' stroke-width='3'/>")
    for x,y,pc in pts: parts.append(f"<circle cx='{x:.1f}' cy='{y:.1f}' r='4.8' fill='#241F20'><title>{pc:.1%}</title></circle>")
    parts += [f"<rect x='{ml}' y='{h-34}' width='16' height='12' fill='#C00031'/><text x='{ml+24}' y='{h-24}' fill='#241F20' font-size='12'>Quantidade</text>",f"<line x1='{ml+125}' y1='{h-28}' x2='{ml+160}' y2='{h-28}' stroke='#241F20' stroke-width='3'/><text x='{ml+168}' y='{h-24}' fill='#241F20' font-size='12'>% acumulado</text>",f"<line x1='{ml+285}' y1='{h-28}' x2='{ml+325}' y2='{h-28}' stroke='#C00031' stroke-width='2.5' stroke-dasharray='8 7'/><text x='{ml+333}' y='{h-24}' fill='#241F20' font-size='12'>Meta 80%</text>","</svg></div>"]
    return ''.join(parts)
def period(df,year,mode):
    ydf=df[df.DT_HR_INSPECAO.dt.year.eq(year)].copy(); mn,mx=ydf.DT_HR_INSPECAO.dt.date.min(),ydf.DT_HR_INSPECAO.dt.date.max()
    if mode=='Diário': d=st.sidebar.date_input('Dia',value=mx,min_value=mn,max_value=mx,format='DD/MM/YYYY'); return ydf,d,d,d.strftime('%d/%m/%Y')
    if mode=='Mensal': months=sorted(ydf.DT_HR_INSPECAO.dt.month.unique()); labels=[f'{m:02d}/{year}' for m in months]; lab=st.sidebar.selectbox('Mês',labels,index=len(labels)-1); m=int(lab[:2]); return ydf,date(year,m,1),date(year,m,monthrange(year,m)[1]),lab
    if mode=='Semanal':
        dates=sorted(ydf.DT_HR_INSPECAO.dt.date.unique()); mons=sorted({d-timedelta(days=d.weekday()) for d in dates}); labels=[f"Semana {i+1:02d} - {m.strftime('%d/%m/%Y')} a {(m+timedelta(days=6)).strftime('%d/%m/%Y')}" for i,m in enumerate(mons)]; lab=st.sidebar.selectbox('Semana',labels,index=len(labels)-1); ix=labels.index(lab); return ydf,mons[ix],mons[ix]+timedelta(days=6),lab
    if mode=='Anual YTD': return ydf,date(year,1,1),mx,f"YTD {year} até {mx.strftime('%d/%m/%Y')}"
    p=st.sidebar.date_input('Período personalizado',value=(mn,mx),min_value=mn,max_value=mx,format='DD/MM/YYYY')
    if isinstance(p,tuple) and len(p)==2: return ydf,p[0],p[1],f"Personalizado {p[0].strftime('%d/%m/%Y')} a {p[1].strftime('%d/%m/%Y')}"
    return ydf,mn,mx,'Personalizado'

def add_percent_cols(df, pct_cols=('Percentual','Percentual Acumulado')):
    out=df.copy()
    for c in pct_cols:
        if c in out.columns: out[c]=out[c].map(fpct)
    return out

c=con(); init(c); st.markdown(CSS,unsafe_allow_html=True)
st.markdown(f"<div class='agco-header'>{logo_html()}<div class='head-title'><h1>Pareto de Falhas QG09</h1><p>Versão {APP_VERSION}: região, matriz, tendência, antes/depois e famílias de defeito.</p><span class='badge'>Região</span><span class='badge'>Matriz</span><span class='badge'>Tendência</span><span class='badge'>Antes x Depois</span><span class='badge'>Famílias</span></div></div>",unsafe_allow_html=True)
df_all=load(c); tabs=st.tabs(['Dashboard','Estratificar TOP','Pareto por Modelo','Região/Estrutura','Matriz Modelo x Falha','Tendência Semanal','Antes x Depois','Famílias de Defeito','Upload','Histórico'])
with st.sidebar:
    top_n=st.slider('Top N',5,25,10)
    if not df_all.empty: years=sorted(df_all.DT_HR_INSPECAO.dt.year.dropna().astype(int).unique()); year=st.selectbox('Ano',years,index=len(years)-1); mode=st.radio('Modo calendário',['Diário','Semanal','Mensal','Anual YTD','Personalizado'])
    else: year=None; mode='Personalizado'
with tabs[8]:
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
    for i in [0,1,2,3,4,5,6,7]:
        with tabs[i]: st.info('Faça upload da base.')
else:
    ydf,start,end,label=period(df_all,year,mode); st.sidebar.divider(); modelos=sorted(df_all.MODELO_CORRIGIDO.dropna().unique()); origens=sorted(df_all.POSTO_ORIGEM_FALHA.dropna().unique()); areas=sorted(df_all.C_AREA_ORIGEM_FALHA.dropna().unique()); ms=st.sidebar.multiselect('Modelo',modelos); osel=st.sidebar.multiselect('Origem',origens); asel=st.sidebar.multiselect('Área',areas)
    filt=ydf[(ydf.DT_HR_INSPECAO>=datetime.combine(start,time(0,0)))&(ydf.DT_HR_INSPECAO<=datetime.combine(end,time(23,59,59)))].copy()
    if ms: filt=filt[filt.MODELO_CORRIGIDO.isin(ms)]
    if osel: filt=filt[filt.POSTO_ORIGEM_FALHA.isin(osel)]
    if asel: filt=filt[filt.C_AREA_ORIGEM_FALHA.isin(asel)]
    pg=pareto(filt,'D1_GERAL',top_n)
    with tabs[0]:
        st.markdown(f"<div class='small-note'>Posto: <b>QG09</b> | Recorte: <b>{label}</b> | Pareto por <b>D1_GERAL</b></div>",unsafe_allow_html=True); a,b,c1,d=st.columns(4); a.markdown(kpi('Falhas',fint(len(filt))),unsafe_allow_html=True); b.markdown(kpi('Top 1',pg.iloc[0].Item if not pg.empty else '-'),unsafe_allow_html=True); c1.markdown(kpi('Qtd Top 1',fint(pg.iloc[0].Quantidade if not pg.empty else 0)),unsafe_allow_html=True); d.markdown(kpi('Modelos',fint(filt.MODELO_CORRIGIDO.nunique())),unsafe_allow_html=True); st.markdown(pareto_svg(pg,f'Pareto Falha Geral - {label}'),unsafe_allow_html=True); show=pg.copy(); show.insert(0,'TOP',range(1,len(show)+1)); st.dataframe(add_percent_cols(show),use_container_width=True,hide_index=True)
    with tabs[1]:
        if pg.empty: st.info('Sem dados.')
        else:
            opts=[f'TOP {i+1} - {r.Item} ({r.Quantidade})' for i,r in pg.reset_index(drop=True).iterrows()]; lab=st.selectbox('Escolha o TOP para estratificar',opts); top=pg.iloc[opts.index(lab)].Item; df_top=filt[filt.D1_GERAL.eq(top)].copy(); st.subheader(lab); bm=pareto(df_top,'MODELO_CORRIGIDO',25); st.markdown('### Distribuição por modelo'); st.markdown(pareto_svg(bm,'Distribuição por modelo'),unsafe_allow_html=True); st.dataframe(add_percent_cols(bm.rename(columns={'Item':'Modelo'})),use_container_width=True,hide_index=True); mod=st.selectbox('Escolha o modelo para ver as informações completas',['Todos']+sorted(df_top.MODELO_CORRIGIDO.dropna().unique())); dfm=df_top.copy() if mod=='Todos' else df_top[df_top.MODELO_CORRIGIDO.eq(mod)].copy(); st.markdown(f"### Ranking das falhas completas - {'Todos os modelos' if mod=='Todos' else mod}"); det=pareto(dfm,'ANOMALIA_FALHA',50).rename(columns={'Item':'Falha completa'})
            if not det.empty:
                det=det[['Falha completa','Quantidade','Percentual','Percentual Acumulado']].copy(); det.insert(0,'Ranking',range(1,len(det)+1)); det['Qtd']=det['Quantidade']; det['Descrição ranking']=det.apply(lambda r:f"{int(r.Ranking)} - {r['Falha completa']} (qtd-{int(r.Qtd)})",axis=1); det_show=add_percent_cols(det)
            else: det_show=det
            st.dataframe(det_show[['Ranking','Falha completa','Qtd','Percentual','Percentual Acumulado','Descrição ranking']] if not det_show.empty else det_show,use_container_width=True,hide_index=True)
            if not det.empty:
                g=det.head(10)[['Falha completa','Qtd']].rename(columns={'Falha completa':'Item','Qtd':'Quantidade'}).copy(); total=float(g['Quantidade'].sum()); g['Percentual']=g['Quantidade']/total if total>0 else 0; g['Percentual Acumulado']=g['Percentual'].cumsum(); st.markdown(pareto_svg(g,'Top 10 falhas completas - Pareto clássico'),unsafe_allow_html=True)
    with tabs[2]:
        st.markdown("<div class='panel'><b>Pareto por Modelo</b><br>Escolha um modelo e veja o Pareto de falha geral dentro dele.</div>",unsafe_allow_html=True); mp=sorted(filt.MODELO_CORRIGIDO.dropna().unique())
        if not mp: st.info('Sem modelos disponíveis no recorte atual.')
        else:
            m=st.selectbox('Modelo para Pareto',mp); dfmp=filt[filt.MODELO_CORRIGIDO.eq(m)].copy(); pm=pareto(dfmp,'D1_GERAL',top_n); x,y,z=st.columns(3); x.markdown(kpi('Modelo',m,'Selecionado'),unsafe_allow_html=True); y.markdown(kpi('Falhas',fint(len(dfmp)),'No recorte'),unsafe_allow_html=True); z.markdown(kpi('Tipos de falha',fint(dfmp.D1_GERAL.nunique()),'D1_GERAL'),unsafe_allow_html=True); st.markdown(pareto_svg(pm,f'Pareto por Modelo - {m} - {label}'),unsafe_allow_html=True); ps=pm.copy(); ps.insert(0,'TOP',range(1,len(ps)+1)); st.dataframe(add_percent_cols(ps),use_container_width=True,hide_index=True)
    with tabs[3]:
        st.markdown("<div class='panel'><b>Estratificação por região da cabine/estrutura</b><br>Extração automática baseada no texto da falha completa.</div>", unsafe_allow_html=True)
        pr=pareto(filt,'REGIAO_EXTRAIDA',top_n); st.markdown(pareto_svg(pr, f'Pareto por Região - {label}'), unsafe_allow_html=True); st.dataframe(add_percent_cols(pr.rename(columns={'Item':'Região'})), use_container_width=True, hide_index=True)
        if not filt.empty:
            regiao_sel=st.selectbox('Escolha uma região para detalhar', sorted(filt.REGIAO_EXTRAIDA.dropna().unique()))
            dfr=filt[filt.REGIAO_EXTRAIDA.eq(regiao_sel)]
            cA,cB=st.columns(2)
            with cA: st.markdown(pareto_svg(pareto(dfr,'D1_GERAL',10), f'Falhas na região: {regiao_sel}'), unsafe_allow_html=True)
            with cB: st.markdown(pareto_svg(pareto(dfr,'MODELO_CORRIGIDO',10), f'Modelos na região: {regiao_sel}'), unsafe_allow_html=True)
    with tabs[4]:
        st.markdown("<div class='panel'><b>Matriz Modelo x Falha</b><br>Mostra concentração de falhas por modelo e tipo geral de defeito.</div>", unsafe_allow_html=True)
        if filt.empty: st.info('Sem dados.')
        else:
            top_falhas = filt.D1_GERAL.value_counts().head(15).index.tolist()
            mat = pd.pivot_table(filt[filt.D1_GERAL.isin(top_falhas)], index='MODELO_CORRIGIDO', columns='D1_GERAL', values='ANOMALIA_FALHA', aggfunc='count', fill_value=0)
            st.dataframe(mat, use_container_width=True)
            st.caption('Quanto maior o número, maior a concentração da falha naquele modelo.')
    with tabs[5]:
        st.markdown("<div class='panel'><b>Tendência semanal por falha escolhida</b><br>Acompanhe se uma falha está subindo, caindo ou estabilizada ao longo das semanas.</div>", unsafe_allow_html=True)
        if filt.empty: st.info('Sem dados.')
        else:
            falha = st.selectbox('Falha geral', sorted(filt.D1_GERAL.dropna().unique()))
            modelos_tend = ['Todos'] + sorted(filt.MODELO_CORRIGIDO.dropna().unique())
            modelo_t = st.selectbox('Modelo para tendência', modelos_tend)
            dft=filt[filt.D1_GERAL.eq(falha)].copy()
            if modelo_t!='Todos': dft=dft[dft.MODELO_CORRIGIDO.eq(modelo_t)]
            trend=dft.groupby('SEMANA_INICIO').size().reset_index(name='Quantidade').sort_values('SEMANA_INICIO')
            st.line_chart(trend.set_index('SEMANA_INICIO')['Quantidade'] if not trend.empty else pd.Series(dtype=int))
            st.dataframe(trend, use_container_width=True, hide_index=True)
    with tabs[6]:
        st.markdown("<div class='panel'><b>Antes x Depois de uma ação</b><br>Escolha uma data de ação e compare o volume antes e depois.</div>", unsafe_allow_html=True)
        if filt.empty: st.info('Sem dados.')
        else:
            col1,col2,col3=st.columns(3)
            with col1: falha_ad=st.selectbox('Falha para comparar', ['Todas']+sorted(filt.D1_GERAL.dropna().unique()))
            with col2: modelo_ad=st.selectbox('Modelo', ['Todos']+sorted(filt.MODELO_CORRIGIDO.dropna().unique()))
            with col3: reg_ad=st.selectbox('Região', ['Todas']+sorted(filt.REGIAO_EXTRAIDA.dropna().unique()))
            min_d,max_d=filt.DT_HR_INSPECAO.dt.date.min(),filt.DT_HR_INSPECAO.dt.date.max()
            acao=st.date_input('Data da ação', value=min(max_d, max(min_d, min_d + (max_d-min_d)//2)), min_value=min_d, max_value=max_d, format='DD/MM/YYYY')
            base=filt.copy()
            if falha_ad!='Todas': base=base[base.D1_GERAL.eq(falha_ad)]
            if modelo_ad!='Todos': base=base[base.MODELO_CORRIGIDO.eq(modelo_ad)]
            if reg_ad!='Todas': base=base[base.REGIAO_EXTRAIDA.eq(reg_ad)]
            antes=base[base.DT_HR_INSPECAO.dt.date < acao]
            depois=base[base.DT_HR_INSPECAO.dt.date >= acao]
            dias_antes=max((acao-min_d).days,1); dias_depois=max((max_d-acao).days+1,1)
            taxa_antes=len(antes)/dias_antes; taxa_depois=len(depois)/dias_depois; reducao=((taxa_depois-taxa_antes)/taxa_antes*100) if taxa_antes else 0
            k1,k2,k3,k4=st.columns(4)
            k1.markdown(kpi('Antes',fint(len(antes)),f'{dias_antes} dias'),unsafe_allow_html=True); k2.markdown(kpi('Depois',fint(len(depois)),f'{dias_depois} dias'),unsafe_allow_html=True); k3.markdown(kpi('Taxa antes',f'{taxa_antes:.2f}/dia'.replace('.',',')),unsafe_allow_html=True); k4.markdown(kpi('Variação taxa',f'{reducao:.1f}%'.replace('.',','),'negativo = redução'),unsafe_allow_html=True)
            comp=pd.DataFrame({'Período':['Antes','Depois'],'Quantidade':[len(antes),len(depois)],'Taxa por dia':[taxa_antes,taxa_depois]})
            st.bar_chart(comp.set_index('Período')['Quantidade'])
            st.dataframe(comp, use_container_width=True, hide_index=True)
    with tabs[7]:
        st.markdown("<div class='panel'><b>Classificação automática de defeitos de solda</b><br>Agrupa defeitos em famílias para leitura executiva.</div>", unsafe_allow_html=True)
        pf=pareto(filt,'FAMILIA_DEFEITO',top_n); st.markdown(pareto_svg(pf, f'Pareto por Família de Defeito - {label}'), unsafe_allow_html=True); st.dataframe(add_percent_cols(pf.rename(columns={'Item':'Família'})), use_container_width=True, hide_index=True)
        if not filt.empty:
            fam=st.selectbox('Escolha uma família para detalhar', sorted(filt.FAMILIA_DEFEITO.dropna().unique()))
            dff=filt[filt.FAMILIA_DEFEITO.eq(fam)]
            st.markdown(pareto_svg(pareto(dff,'D1_GERAL',15), f'Detalhe da família: {fam}'), unsafe_allow_html=True)
            st.dataframe(dff[['DT_HR_INSPECAO','MODELO_CORRIGIDO','REGIAO_EXTRAIDA','D1_GERAL','ANOMALIA_FALHA','POSTO_ORIGEM_FALHA']].sort_values('DT_HR_INSPECAO'), use_container_width=True, hide_index=True)
with tabs[9]:
    st.dataframe(hist(c),use_container_width=True,hide_index=True)
    if st.button('Limpar calendário inteiro'): clear(c); st.rerun()
