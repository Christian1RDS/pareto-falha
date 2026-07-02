
import io, os, re, base64, sqlite3, unicodedata, html
from datetime import datetime, date, time, timedelta
from calendar import monthrange
import pandas as pd
import streamlit as st

st.set_page_config(page_title="AGCO | Pareto QG09 V0.21", page_icon="📊", layout="wide")
APP_VERSION = "V0.21"
DB = "pareto_qg09_v021.db"
POSTO_FIXO = "QG09"
LOGOS = ["agco_logo.png","AGCO_logo.png","agco-logo.png","logo_agco.png","logo.png","AGCO.png","agco.png","agco_corporate_logo.png","AGCO_Corporate_Logo.png"]
MAPA_MODELOS = {"VTBAGFC":"VTBA", "V2MFGFC":"V2 MF", "V2VTGFC":"V2 VT", "G7GFCAN":"G7", "G8GFCAN":"G8"}
REQ = ["CD_POSTO_CN","CD_MODELO","DT_HR_INSPECAO","ANOMALIA_FALHA"]
OPT = ["D1","NR_WO","NR_SERIE","POSTO_ORIGEM_FALHA","C_AREA_ORIGEM_FALHA","C_DPU_QG_AMARELO"]
ALIASES = {
    "CD_POSTO_CN":["CD_POSTO_CN","CD_POSTO_FALHA","POSTO","POSTO_CN","CD_POSTO"],
    "CD_MODELO":["CD_MODELO","MODELO","COD_MODELO"],
    "DT_HR_INSPECAO":["DT_HR_INSPECAO","DT_CRIACAO_FALHA","DT_ENC_CERTIFICADO","DT_ENCERRAMENTO_FALHA","DATA_INSPECAO","DATA"],
    "ANOMALIA_FALHA":["ANOMALIA_FALHA","FALHA","ANOMALIA","DESCRICAO_FALHA"],
    "D1":["D1"], "NR_WO":["NR_WO","WO","ORDEM"], "NR_SERIE":["NR_SERIE","SERIE","CHASSI"],
    "POSTO_ORIGEM_FALHA":["POSTO_ORIGEM_FALHA","ORIGEM_FALHA","POSTO_ORIGEM","ORIGEM"],
    "C_AREA_ORIGEM_FALHA":["C_AREA_ORIGEM_FALHA","AREA_ORIGEM_FALHA","AREA_ORIGEM"],
}

CSS = """
<style>
:root{--red:#C00031;--black:#241F20;--panel:#181A1D;--panel2:#202327;--border:#3A3D42;--muted:#B7BDC6;--text:#F4F5F7;}
.stApp{background:linear-gradient(180deg,#101113 0%,#17191C 100%);color:var(--text);} 
[data-testid="stSidebar"]{background:linear-gradient(180deg,#241F20 0%,#151315 100%);border-right:5px solid var(--red);}
[data-testid="stSidebar"] *{color:#fff!important}.block-container{padding-top:1rem;}
.agco-header{display:flex;gap:20px;align-items:center;padding:22px 26px;border:1px solid var(--border);background:linear-gradient(135deg,#241F20 0%,#181A1D 62%,#3a0b16 100%);border-radius:12px;box-shadow:0 14px 34px rgba(0,0,0,.30);border-top:6px solid var(--red);margin-bottom:18px;}
.logo-box{background:#fff;padding:8px 12px;border-radius:4px;display:flex;align-items:center;justify-content:center;min-width:145px;min-height:58px;}.brand-word{font-size:2.15rem;font-weight:950;color:#241F20}.brand-sub{font-size:.72rem;color:#241F20;text-transform:uppercase;letter-spacing:1.4px}.head-title h1{margin:0;color:#fff;font-size:2rem}.head-title p{color:var(--muted);margin:6px 0 0}.badge{display:inline-block;padding:5px 10px;border-radius:4px;border:1px solid rgba(255,255,255,.18);background:rgba(192,0,49,.22);color:#fff;font-weight:800;font-size:.78rem;margin-right:6px;margin-top:8px;text-transform:uppercase}.panel{background:var(--panel);border:1px solid var(--border);border-left:5px solid var(--red);border-radius:10px;padding:18px;box-shadow:0 10px 24px rgba(0,0,0,.25);margin-bottom:16px}.kpi{background:linear-gradient(180deg,var(--panel2),var(--panel));border:1px solid var(--border);border-top:4px solid var(--red);border-radius:10px;padding:18px;min-height:112px}.kpi-label{color:var(--muted);font-size:.80rem;font-weight:900;text-transform:uppercase}.kpi-value{color:#fff;font-size:1.55rem;font-weight:900;margin-top:8px}.kpi-sub{color:var(--muted);font-size:.85rem}.pareto-box{background:#fff;border:1px solid var(--border);border-radius:10px;padding:14px;overflow-x:auto}.small-note{color:#fff;background:var(--panel);border:1px solid var(--border);border-left:5px solid var(--red);padding:10px 12px;border-radius:8px;margin-bottom:12px}svg text{font-family:Arial,Helvetica,sans-serif}.stDataFrame{background:#fff!important}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

def logo_html():
    for f in LOGOS:
        if os.path.exists(f):
            ext = os.path.splitext(f)[1].lower().replace('.','')
            mime = 'jpeg' if ext in ['jpg','jpeg'] else 'png'
            b64 = base64.b64encode(open(f,'rb').read()).decode('utf-8')
            return f"<div class='logo-box'><img src='data:image/{mime};base64,{b64}' style='max-height:58px;max-width:180px;object-fit:contain;'/></div>"
    return "<div class='logo-box'><div><div class='brand-word'>AGCO</div><div class='brand-sub'>Corporation</div></div></div>"

def strip_accents(t): return ''.join(ch for ch in unicodedata.normalize('NFKD', str(t)) if not unicodedata.combining(ch))
def clean_col(c):
    t = strip_accents(str(c).replace('\\_','_').replace('\\','').strip()).upper()
    t = re.sub(r'[^A-Z0-9]+','_',t)
    return re.sub(r'_+','_',t).strip('_')
def txt(v): return '' if pd.isna(v) else re.sub(r'\s+',' ',str(v).strip())
def norm_cols(df):
    df=df.copy(); orig=list(df.columns); df.columns=[clean_col(c) for c in df.columns]
    ex=set(df.columns); ren={}
    for can, als in ALIASES.items():
        if can in ex: continue
        for a in als:
            ca=clean_col(a)
            if ca in ex:
                ren[ca]=can; break
    if ren: df=df.rename(columns=ren)
    return df.loc[:,~df.columns.duplicated()].copy(), orig, list(df.columns)
def corr_modelo(v):
    c=txt(v).upper(); return MAPA_MODELOS.get(c,c or 'Não informado')
def falha_geral(d1, anom):
    v=(txt(d1) or txt(anom)).upper()
    v=re.sub(r'^(SOLDA|PE[CÇ]A|COMPONENTE)\s*[-–—]\s*','',v).strip()
    v=re.sub(r'^SOLDA\s+','',v).strip()
    return v or 'NÃO INFORMADO'
def extrai_regiao(anom):
    a=strip_accents(txt(anom)).upper()
    checks=[('FECHAMENTO SUPERIOR','FECHAMENTO SUPERIOR'),('ESTR. TRASEIRA','ESTRUTURA TRASEIRA'),('ESTR TRASEIRA','ESTRUTURA TRASEIRA'),('ESTR. PARALAMAS','ESTRUTURA PARALAMAS'),('LATERAL ESQUERDA','LATERAL ESQUERDA'),('LAT ESQ','LATERAL ESQUERDA'),('LATERAL DIREITA','LATERAL DIREITA'),('LAT DIR','LATERAL DIREITA'),('ASSOALHO','ASSOALHO'),('PISO','ASSOALHO/PISO'),('TETO','TETO'),('SUPERIOR','SUPERIOR'),('TRASEIRA','TRASEIRA'),('FRONTAL','FRONTAL'),('FRENTE','FRONTAL'),('INFERIOR','INFERIOR'),('PARALAMAS','PARALAMAS')]
    for k,v in checks:
        if k in a: return v
    return 'NÃO CLASSIFICADO'
def familia_defeito(d1, anom):
    d=strip_accents((txt(d1) or txt(anom))).upper()
    if any(x in d for x in ['RESPING','CORDAO','FALTA CORDAO','POROSIDADE','FUSAO','PENETRACAO','SOLDA']): return 'SOLDA'
    if any(x in d for x in ['ACABAMENTO','OXIDADO','PINTURA']): return 'ACABAMENTO / SUPERFÍCIE'
    if any(x in d for x in ['FALTA COMPONENTE','PECA ERRADA','COMPONENTE FORA','FALTA MONTAR']): return 'COMPONENTE / MONTAGEM'
    if any(x in d for x in ['DESALINHADO','TORTO','TORCIDO','CURTO','TENSIONADO','FORA DE POSICAO']): return 'DIMENSIONAL / POSIÇÃO'
    if any(x in d for x in ['DANIFICADO','QUEBRADO','CORTADO','TRINCADO']): return 'DANO'
    return 'OUTROS'
def parse_dt(s):
    dt=pd.to_datetime(s,errors='coerce')
    m=dt.isna() & s.notna()
    if m.any(): dt.loc[m]=pd.to_datetime(s[m],errors='coerce',dayfirst=True)
    return dt
def enrich(df):
    if df.empty: return df
    df=df.copy()
    df['REGIAO_EXTRAIDA']=df.ANOMALIA_FALHA.map(extrai_regiao)
    df['FAMILIA_DEFEITO']=df.apply(lambda r: familia_defeito(r.get('D1',''),r.get('ANOMALIA_FALHA','')),axis=1)
    df['SEMANA_INICIO']=df.DT_HR_INSPECAO.dt.to_period('W-MON').apply(lambda r: r.start_time.date() if pd.notna(r.start_time) else None)
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
    return norm_cols(pd.read_excel(io.BytesIO(data),engine='openpyxl' if ext=='xlsx' else 'xlrd',dtype=str))
def prepare(raw):
    df=raw.copy(); miss=[c for c in REQ if c not in df.columns]
    if miss: raise ValueError('Colunas obrigatórias ausentes: '+', '.join(miss))
    for c in OPT:
        if c not in df.columns: df[c]=''
    df['CD_POSTO_CN']=df.CD_POSTO_CN.map(lambda x:'QG09' if 'QG09' in txt(x).upper() else txt(x).upper())
    df['CD_MODELO']=df.CD_MODELO.map(lambda x:txt(x).upper())
    df['MODELO_CORRIGIDO']=df.CD_MODELO.map(corr_modelo)
    df['DT_HR_INSPECAO']=parse_dt(df.DT_HR_INSPECAO)
    df['ANOMALIA_FALHA']=df.ANOMALIA_FALHA.map(txt)
    df['D1']=df.D1.map(txt)
    df['D1_GERAL']=df.apply(lambda r: falha_geral(r.D1,r.ANOMALIA_FALHA),axis=1)
    for c in ['NR_WO','NR_SERIE','POSTO_ORIGEM_FALHA','C_AREA_ORIGEM_FALHA']: df[c]=df[c].map(txt)
    q=df[df.CD_POSTO_CN.eq(POSTO_FIXO)&df.DT_HR_INSPECAO.notna()].copy()
    f=q[q.ANOMALIA_FALHA.ne('')].copy()
    cols=['NR_WO','NR_SERIE','CD_MODELO','MODELO_CORRIGIDO','DT_HR_INSPECAO','ANOMALIA_FALHA','D1','D1_GERAL','POSTO_ORIGEM_FALHA','C_AREA_ORIGEM_FALHA']
    return df,enrich(q[cols]),enrich(f[cols])

def con(): return sqlite3.connect(DB,check_same_thread=False)
def init(c):
    c.execute('CREATE TABLE IF NOT EXISTS upload_log(id INTEGER PRIMARY KEY AUTOINCREMENT,file_name TEXT,uploaded_at TEXT,total_rows INTEGER,qg09_rows INTEGER,falhas_rows INTEGER,min_date TEXT,max_date TEXT,mode TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS falhas_qg09(id INTEGER PRIMARY KEY AUTOINCREMENT,nr_wo TEXT,nr_serie TEXT,cd_modelo TEXT,modelo_corrigido TEXT,dt_hr_inspecao TEXT,anomalia_falha TEXT,d1 TEXT,d1_geral TEXT,posto_origem_falha TEXT,c_area_origem_falha TEXT)')
    c.commit()
def save(c,name,full,qg09,falhas):
    mind=falhas.DT_HR_INSPECAO.dt.date.min().isoformat() if not falhas.empty else None
    maxd=falhas.DT_HR_INSPECAO.dt.date.max().isoformat() if not falhas.empty else None
    c.execute('INSERT INTO upload_log(file_name,uploaded_at,total_rows,qg09_rows,falhas_rows,min_date,max_date,mode) VALUES(?,?,?,?,?,?,?,?)',(name,datetime.now().isoformat(timespec='seconds'),len(full),len(qg09),len(falhas),mind,maxd,'Somar ao calendário'))
    rows=[(r.NR_WO,r.NR_SERIE,r.CD_MODELO,r.MODELO_CORRIGIDO,r.DT_HR_INSPECAO.isoformat(sep=' ',timespec='seconds'),r.ANOMALIA_FALHA,r.D1,r.D1_GERAL,r.POSTO_ORIGEM_FALHA,r.C_AREA_ORIGEM_FALHA) for _,r in falhas.iterrows()]
    c.executemany('INSERT INTO falhas_qg09(nr_wo,nr_serie,cd_modelo,modelo_corrigido,dt_hr_inspecao,anomalia_falha,d1,d1_geral,posto_origem_falha,c_area_origem_falha) VALUES(?,?,?,?,?,?,?,?,?,?)',rows); c.commit()
def load(c):
    df=pd.read_sql_query('SELECT nr_wo NR_WO,nr_serie NR_SERIE,cd_modelo CD_MODELO,modelo_corrigido MODELO_CORRIGIDO,dt_hr_inspecao DT_HR_INSPECAO,anomalia_falha ANOMALIA_FALHA,d1 D1,d1_geral D1_GERAL,posto_origem_falha POSTO_ORIGEM_FALHA,c_area_origem_falha C_AREA_ORIGEM_FALHA FROM falhas_qg09',c)
    if df.empty: return df
    df.DT_HR_INSPECAO=pd.to_datetime(df.DT_HR_INSPECAO,errors='coerce')
    df.D1=df.D1.fillna('').astype(str)
    df.D1_GERAL=df.apply(lambda r: txt(r.D1_GERAL) or falha_geral(r.D1,r.ANOMALIA_FALHA),axis=1)
    return enrich(df.drop_duplicates())
def hist(c): return pd.read_sql_query('SELECT * FROM upload_log ORDER BY id DESC',c)
def clear(c): c.execute('DELETE FROM falhas_qg09'); c.execute('DELETE FROM upload_log'); c.commit()

def fmt_int(v): return f'{int(v):,}'.replace(',','.') if pd.notna(v) else '0'
def fmt_pct(v): return f'{float(v)*100:.1f}%'.replace('.',',')
def kpi(l,v,s=''): return f"<div class='kpi'><div class='kpi-label'>{html.escape(str(l))}</div><div class='kpi-value'>{html.escape(str(v))}</div><div class='kpi-sub'>{html.escape(str(s))}</div></div>"
def pareto(df,col,n=10):
    if df.empty or col not in df: return pd.DataFrame(columns=['Item','Quantidade','Percentual','Percentual Acumulado'])
    s=df[col].fillna('').astype(str).str.strip(); s=s[s.ne('')]
    if s.empty: return pd.DataFrame(columns=['Item','Quantidade','Percentual','Percentual Acumulado'])
    out=s.value_counts().head(n).reset_index(); out.columns=['Item','Quantidade']; total=out.Quantidade.sum(); out['Percentual']=out.Quantidade/total if total else 0; out['Percentual Acumulado']=out.Percentual.cumsum(); return out
def pareto_svg(p,title):
    if p.empty: return "<div class='pareto-box'>Sem dados.</div>"
    p=p.copy().reset_index(drop=True); w,h,ml,mr,mt,mb=1220,600,80,90,62,175; pw=w-ml-mr; ph=h-mt-mb; mx=max(float(p.Quantidade.max()),1); step=pw/max(len(p),1); bw=min(step*.68,74)
    def yp(pc): return mt+ph-float(pc)*ph
    parts=[f"<div class='pareto-box'><svg viewBox='0 0 {w} {h}' width='100%' height='{h}'>","<rect width='100%' height='100%' fill='#FFFFFF'/>",f"<text x='{ml}' y='35' fill='#241F20' font-size='22' font-weight='800'>{html.escape(title)}</text>"]
    for k in range(6):
        y=mt+ph-(mx*k/5/mx)*ph
        parts += [f"<line x1='{ml}' y1='{y:.1f}' x2='{w-mr}' y2='{y:.1f}' stroke='#E2E5E9'/>",f"<text x='{ml-12}' y='{y+4:.1f}' fill='#657080' font-size='12' text-anchor='end'>{int(round(mx*k/5))}</text>",f"<text x='{w-mr+12}' y='{y+4:.1f}' fill='#657080' font-size='12'>{k*20}%</text>"]
    y80=yp(.8); parts += [f"<line x1='{ml}' y1='{y80:.1f}' x2='{w-mr}' y2='{y80:.1f}' stroke='#C00031' stroke-width='2.5' stroke-dasharray='8 7'/>",f"<text x='{w-mr-6}' y='{y80-8:.1f}' fill='#C00031' font-size='14' font-weight='800' text-anchor='end'>80%</text>"]
    pts=[]
    for i,r in p.iterrows():
        x=ml+step*i+step/2; bh=(r.Quantidade/mx)*ph; y=mt+ph-bh; lab=str(r.Item); short=lab[:28]+('...' if len(lab)>28 else '')
        parts += [f"<rect x='{x-bw/2:.1f}' y='{y:.1f}' width='{bw:.1f}' height='{bh:.1f}' fill='#C00031' rx='3'><title>{html.escape(lab)} - {int(r.Quantidade)}</title></rect>",f"<text x='{x:.1f}' y='{max(y-7,48):.1f}' fill='#241F20' font-size='12' font-weight='700' text-anchor='middle'>{int(r.Quantidade)}</text>",f"<text x='{x:.1f}' y='{mt+ph+26}' fill='#657080' font-size='11' text-anchor='end' transform='rotate(-35 {x:.1f} {mt+ph+26})'>{html.escape(short)}</text>"]
        pts.append((x,yp(r['Percentual Acumulado'])))
    parts.append("<polyline points='"+' '.join(f'{x:.1f},{y:.1f}' for x,y in pts)+"' fill='none' stroke='#241F20' stroke-width='3'/>")
    for x,y in pts: parts.append(f"<circle cx='{x:.1f}' cy='{y:.1f}' r='4.8' fill='#241F20'/>")
    parts.append('</svg></div>'); return ''.join(parts)
def show_table(p):
    out=p.copy()
    if not out.empty:
        if 'Percentual' in out: out['Percentual']=out.Percentual.map(fmt_pct)
        if 'Percentual Acumulado' in out: out['Percentual Acumulado']=out['Percentual Acumulado'].map(fmt_pct)
    st.dataframe(out,use_container_width=True,hide_index=True)
def period(df,year,mode):
    ydf=df[df.DT_HR_INSPECAO.dt.year.eq(year)].copy(); mn,mx=ydf.DT_HR_INSPECAO.dt.date.min(),ydf.DT_HR_INSPECAO.dt.date.max()
    if mode=='Diário': d=st.sidebar.date_input('Dia',value=mx,min_value=mn,max_value=mx,format='DD/MM/YYYY'); return ydf,d,d,d.strftime('%d/%m/%Y')
    if mode=='Mensal': months=sorted(ydf.DT_HR_INSPECAO.dt.month.unique()); labels=[f'{m:02d}/{year}' for m in months]; lab=st.sidebar.selectbox('Mês',labels,index=len(labels)-1); m=int(lab[:2]); return ydf,date(year,m,1),date(year,m,monthrange(year,m)[1]),lab
    if mode=='Anual YTD': return ydf,date(year,1,1),mx,f"YTD {year} até {mx.strftime('%d/%m/%Y')}"
    p=st.sidebar.date_input('Período personalizado',value=(mn,mx),min_value=mn,max_value=mx,format='DD/MM/YYYY')
    if isinstance(p,tuple) and len(p)==2: return ydf,p[0],p[1],f"Personalizado {p[0].strftime('%d/%m/%Y')} a {p[1].strftime('%d/%m/%Y')}"
    return ydf,mn,mx,'Personalizado'
def criticidade(df):
    if df.empty: return pd.DataFrame(columns=['Falha','Quantidade','Modelos afetados','Regiões afetadas','Tendência %','Estabilidade','Score criticidade','Criticidade'])
    wk=df.groupby(['D1_GERAL','SEMANA_INICIO']).size().reset_index(name='Quantidade').sort_values(['D1_GERAL','SEMANA_INICIO'])
    rows=[]
    for falha,g in wk.groupby('D1_GERAL'):
        dff=df[df.D1_GERAL.eq(falha)]; qtd=int(g.Quantidade.sum()); modelos=dff.MODELO_CORRIGIDO.nunique(); regs=dff.REGIAO_EXTRAIDA.nunique()
        if len(g)<3: status='Sem histórico suficiente'; trend=0
        else:
            ult=float(g.Quantidade.tail(2).mean()); ant=float(g.Quantidade.head(max(len(g)-2,1)).mean()); trend=((ult-ant)/ant*100) if ant else 0
            if trend>=25: status='Em crescimento'
            elif trend<=-25: status='Em queda'
            elif g.Quantidade.std()>g.Quantidade.mean()*0.7: status='Instável'
            else: status='Estável'
        score=qtd+modelos*8+regs*5+max(trend,0)*1.5
        cls='Crítica' if score>=120 else 'Alta' if score>=70 else 'Média' if score>=30 else 'Baixa'
        rows.append([falha,qtd,modelos,regs,round(trend,1),status,round(score,1),cls])
    return pd.DataFrame(rows,columns=['Falha','Quantidade','Modelos afetados','Regiões afetadas','Tendência %','Estabilidade','Score criticidade','Criticidade']).sort_values('Score criticidade',ascending=False)
def score_pareto(crit):
    if crit.empty: return pd.DataFrame(columns=['Item','Quantidade','Percentual','Percentual Acumulado'])
    p=crit[['Falha','Score criticidade']].rename(columns={'Falha':'Item','Score criticidade':'Quantidade'}).head(15).copy(); total=p.Quantidade.sum(); p['Percentual']=p.Quantidade/total if total else 0; p['Percentual Acumulado']=p.Percentual.cumsum(); return p

db=con(); init(db)
st.markdown(f"<div class='agco-header'>{logo_html()}<div class='head-title'><h1>Pareto de Falhas QG09</h1><p>Versão {APP_VERSION}: cópia limpa baseada na V0.18 correta, mantendo os Paretos clássicos.</p><span class='badge'>Base V0.18</span><span class='badge'>Pareto clássico</span><span class='badge'>Clean</span></div></div>",unsafe_allow_html=True)
df_all=load(db)
tabs=st.tabs(['Dashboard','Estratificar TOP','Pareto por Modelo','Região/Estrutura','Matriz Modelo x Falha','Tendência Semanal','Antes x Depois','Famílias de Defeito','Criticidade/Estabilidade','Upload','Histórico'])
with st.sidebar:
    top_n=st.slider('Top N',5,25,10)
    if not df_all.empty:
        years=sorted(df_all.DT_HR_INSPECAO.dt.year.dropna().astype(int).unique()); year=st.selectbox('Ano',years,index=len(years)-1); mode=st.radio('Modo calendário',['Diário','Mensal','Anual YTD','Personalizado'])
    else: year=None; mode='Personalizado'
with tabs[9]:
    st.markdown("<div class='panel'><b>Upload</b><br>Versão limpa baseada na V0.18. Sem alertas/foco e sem alterações da V0.19/V0.20.</div>",unsafe_allow_html=True)
    up=st.file_uploader('Base (.csv, .xlsx ou .xls)',type=['csv','xlsx','xls'])
    if up:
        try:
            raw,orig,final=read_file(up); full,qg09,falhas=prepare(raw)
            st.success(f'Arquivo lido: {up.name} | Linhas: {len(full)} | QG09: {len(qg09)} | Falhas QG09: {len(falhas)}')
            with st.expander('Diagnóstico de cabeçalhos'): st.write('Originais',orig); st.write('Normalizados',final)
            st.dataframe(falhas.head(200),use_container_width=True,hide_index=True)
            if st.button('Salvar no calendário',type='primary') and not falhas.empty:
                save(db,up.name,full,qg09,falhas); st.rerun()
        except Exception as e: st.error(str(e))
df_all=load(db)
if df_all.empty or year is None:
    for i in range(9):
        with tabs[i]: st.info('Faça upload da base.')
else:
    ydf,start,end,label=period(df_all,year,mode)
    modelos=sorted(df_all.MODELO_CORRIGIDO.dropna().unique()); origens=sorted(df_all.POSTO_ORIGEM_FALHA.dropna().unique()); areas=sorted(df_all.C_AREA_ORIGEM_FALHA.dropna().unique())
    st.sidebar.divider(); ms=st.sidebar.multiselect('Modelo',modelos); osel=st.sidebar.multiselect('Origem',origens); asel=st.sidebar.multiselect('Área',areas)
    filt=ydf[(ydf.DT_HR_INSPECAO>=datetime.combine(start,time(0,0)))&(ydf.DT_HR_INSPECAO<=datetime.combine(end,time(23,59,59)))].copy()
    if ms: filt=filt[filt.MODELO_CORRIGIDO.isin(ms)]
    if osel: filt=filt[filt.POSTO_ORIGEM_FALHA.isin(osel)]
    if asel: filt=filt[filt.C_AREA_ORIGEM_FALHA.isin(asel)]
    pg=pareto(filt,'D1_GERAL',top_n)
    with tabs[0]:
        st.markdown(f"<div class='small-note'>Posto: <b>QG09</b> | Recorte: <b>{label}</b> | Pareto por <b>D1_GERAL</b></div>",unsafe_allow_html=True)
        a,b,c,d=st.columns(4); a.markdown(kpi('Falhas',fmt_int(len(filt))),unsafe_allow_html=True); b.markdown(kpi('Top 1',pg.iloc[0].Item if not pg.empty else '-'),unsafe_allow_html=True); c.markdown(kpi('Modelos',fmt_int(filt.MODELO_CORRIGIDO.nunique())),unsafe_allow_html=True); d.markdown(kpi('Regiões',fmt_int(filt.REGIAO_EXTRAIDA.nunique())),unsafe_allow_html=True)
        st.markdown(pareto_svg(pg,f'Pareto Falha Geral - {label}'),unsafe_allow_html=True); show_table(pg)
    with tabs[1]:
        if pg.empty: st.info('Sem dados.')
        else:
            opts=[f'TOP {i+1} - {r.Item} ({r.Quantidade})' for i,r in pg.reset_index(drop=True).iterrows()]; lab=st.selectbox('Escolha o TOP para estratificar',opts); top=pg.iloc[opts.index(lab)].Item; df_top=filt[filt.D1_GERAL.eq(top)].copy(); st.subheader(lab)
            bm=pareto(df_top,'MODELO_CORRIGIDO',25); st.markdown(pareto_svg(bm,'Distribuição por modelo'),unsafe_allow_html=True); show_table(bm.rename(columns={'Item':'Modelo'}))
            det=pareto(df_top,'ANOMALIA_FALHA',50).rename(columns={'Item':'Falha completa'}); st.markdown('### Ranking das falhas completas'); show_table(det)
            if not det.empty:
                g=det.head(10).rename(columns={'Falha completa':'Item'}); st.markdown(pareto_svg(g,'Top 10 falhas completas - Pareto clássico'),unsafe_allow_html=True)
    with tabs[2]:
        mp=sorted(filt.MODELO_CORRIGIDO.dropna().unique())
        if not mp: st.info('Sem modelos disponíveis.')
        else:
            m=st.selectbox('Modelo para Pareto',mp); pm=pareto(filt[filt.MODELO_CORRIGIDO.eq(m)],'D1_GERAL',top_n); st.markdown(pareto_svg(pm,f'Pareto por Modelo - {m} - {label}'),unsafe_allow_html=True); show_table(pm)
    with tabs[3]:
        pr=pareto(filt,'REGIAO_EXTRAIDA',top_n); st.markdown(pareto_svg(pr,f'Pareto por Região - {label}'),unsafe_allow_html=True); show_table(pr.rename(columns={'Item':'Região'}))
    with tabs[4]:
        top_f=filt.D1_GERAL.value_counts().head(15).index.tolist(); mat=pd.pivot_table(filt[filt.D1_GERAL.isin(top_f)],index='MODELO_CORRIGIDO',columns='D1_GERAL',values='ANOMALIA_FALHA',aggfunc='count',fill_value=0); st.dataframe(mat,use_container_width=True)
    with tabs[5]:
        if filt.empty: st.info('Sem dados.')
        else:
            fal=st.selectbox('Falha geral', sorted(filt.D1_GERAL.dropna().unique())); dft=filt[filt.D1_GERAL.eq(fal)].groupby('SEMANA_INICIO').size().reset_index(name='Quantidade').sort_values('SEMANA_INICIO'); st.line_chart(dft.set_index('SEMANA_INICIO')['Quantidade'] if not dft.empty else pd.Series(dtype=int)); st.dataframe(dft,use_container_width=True,hide_index=True)
    with tabs[6]:
        if filt.empty: st.info('Sem dados.')
        else:
            acao=st.date_input('Data da ação',value=filt.DT_HR_INSPECAO.dt.date.max(),min_value=filt.DT_HR_INSPECAO.dt.date.min(),max_value=filt.DT_HR_INSPECAO.dt.date.max(),format='DD/MM/YYYY'); antes=len(filt[filt.DT_HR_INSPECAO.dt.date<acao]); depois=len(filt[filt.DT_HR_INSPECAO.dt.date>=acao]); st.bar_chart(pd.Series({'Antes':antes,'Depois':depois}))
    with tabs[7]:
        pf=pareto(filt,'FAMILIA_DEFEITO',top_n); st.markdown(pareto_svg(pf,f'Pareto por Família de Defeito - {label}'),unsafe_allow_html=True); show_table(pf.rename(columns={'Item':'Família'}))
    with tabs[8]:
        crit=criticidade(filt); st.markdown("<div class='panel'><b>Índice de criticidade + controle de estabilidade</b><br>Base V0.18 limpa, mantendo Pareto clássico por score de criticidade.</div>",unsafe_allow_html=True)
        pcrit=score_pareto(crit); st.markdown(pareto_svg(pcrit,'Pareto de Criticidade da Falha'),unsafe_allow_html=True); show_table(pcrit); st.dataframe(crit,use_container_width=True,hide_index=True)
with tabs[10]:
    st.dataframe(hist(db),use_container_width=True,hide_index=True)
    if st.button('Limpar calendário inteiro'): clear(db); st.rerun()
