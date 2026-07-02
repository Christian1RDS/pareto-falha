
import io, os, re, base64, sqlite3, unicodedata
from datetime import datetime, date, time
from calendar import monthrange
import pandas as pd
import streamlit as st

APP_VERSION="V0.18"
DB="pareto_qg09_v018.db"
FEATURE_LEVEL=18
POSTO_FIXO="QG09"
LOGOS=["agco_logo.png","AGCO_logo.png","agco-logo.png","logo_agco.png","logo.png","AGCO.png","agco.png"]
MAPA_MODELOS={"VTBAGFC":"VTBA","V2MFGFC":"V2 MF","V2VTGFC":"V2 VT","G7GFCAN":"G7","G8GFCAN":"G8"}
REQ=["CD_POSTO_CN","CD_MODELO","DT_HR_INSPECAO","ANOMALIA_FALHA"]
OPTIONAL=["D1","NR_WO","NR_SERIE","POSTO_ORIGEM_FALHA","C_AREA_ORIGEM_FALHA","C_DPU_QG_AMARELO"]
ALIASES={
"CD_POSTO_CN":["CD_POSTO_CN","CD_POSTO_FALHA","POSTO","POSTO_CN","CD_POSTO"],
"CD_MODELO":["CD_MODELO","MODELO","COD_MODELO"],
"DT_HR_INSPECAO":["DT_HR_INSPECAO","DT_CRIACAO_FALHA","DT_ENC_CERTIFICADO","DT_ENCERRAMENTO_FALHA","DATA_INSPECAO","DATA"],
"ANOMALIA_FALHA":["ANOMALIA_FALHA","FALHA","ANOMALIA","DESCRICAO_FALHA"],
"D1":["D1"],"NR_WO":["NR_WO","WO","ORDEM"],"NR_SERIE":["NR_SERIE","SERIE","CHASSI"],
"POSTO_ORIGEM_FALHA":["POSTO_ORIGEM_FALHA","ORIGEM_FALHA","POSTO_ORIGEM","ORIGEM"],
"C_AREA_ORIGEM_FALHA":["C_AREA_ORIGEM_FALHA","AREA_ORIGEM_FALHA","AREA_ORIGEM"]}

st.set_page_config(page_title=f"AGCO | Pareto QG09 {APP_VERSION}", page_icon="📊", layout="wide")
st.markdown("""
<style>
.stApp{background:linear-gradient(180deg,#101113,#17191C);color:#F4F5F7}[data-testid="stSidebar"]{background:#241F20;border-right:5px solid #C00031}[data-testid="stSidebar"] *{color:#fff!important}.head{display:flex;gap:20px;align-items:center;background:linear-gradient(135deg,#241F20,#181A1D,#3a0b16);border-top:6px solid #C00031;border-radius:12px;padding:22px;margin-bottom:18px}.logo{background:white;padding:8px 12px;border-radius:4px;min-width:145px;text-align:center}.logo-t{font-size:2rem;font-weight:900;color:#241F20}.logo-s{font-size:.72rem;color:#241F20;letter-spacing:1px;text-transform:uppercase}.badge{display:inline-block;background:rgba(192,0,49,.25);border:1px solid rgba(255,255,255,.2);border-radius:4px;padding:5px 10px;margin:8px 6px 0 0;font-size:.78rem;font-weight:800}.panel{background:#181A1D;border:1px solid #3A3D42;border-left:5px solid #C00031;border-radius:10px;padding:16px;margin-bottom:16px}.kpi{background:#202327;border-top:4px solid #C00031;border-radius:10px;padding:15px}.kpi-l{color:#B7BDC6;font-size:.78rem;font-weight:900;text-transform:uppercase}.kpi-v{font-size:1.55rem;font-weight:900;color:white}.kpi-s{color:#B7BDC6;font-size:.85rem}
</style>
""", unsafe_allow_html=True)

def logo_html():
    for f in LOGOS:
        if os.path.exists(f):
            ext=os.path.splitext(f)[1].lower().replace('.','')
            mime='jpeg' if ext in ['jpg','jpeg'] else 'png'
            b64=base64.b64encode(open(f,'rb').read()).decode()
            return f"<div class='logo'><img src='data:image/{mime};base64,{b64}' style='max-height:58px;max-width:180px;object-fit:contain'></div>"
    return "<div class='logo'><div class='logo-t'>AGCO</div><div class='logo-s'>Corporation</div></div>"

def strip_accents(t): return ''.join(ch for ch in unicodedata.normalize('NFKD',str(t)) if not unicodedata.combining(ch))
def clean_col(c):
    t=strip_accents(str(c).replace('\\_','_').replace('\\','').strip()).upper(); t=re.sub(r'[^A-Z0-9]+','_',t); return re.sub(r'_+','_',t).strip('_')
def txt(v): return '' if pd.isna(v) else re.sub(r'\s+',' ',str(v).strip())
def normalize_columns(df):
    df=df.copy(); orig=list(df.columns); df.columns=[clean_col(c) for c in df.columns]; ex=set(df.columns); ren={}
    for can,als in ALIASES.items():
        if can in ex: continue
        for a in als:
            ca=clean_col(a)
            if ca in ex: ren[ca]=can; break
    if ren: df=df.rename(columns=ren)
    return df.loc[:,~df.columns.duplicated()].copy(), orig, list(df.columns)
def corr_modelo(v):
    c=txt(v).upper(); return MAPA_MODELOS.get(c,c or 'Não informado')
def falha_geral(d1, anom):
    v=(txt(d1) or txt(anom)).upper(); v=re.sub(r'^(SOLDA|PE[CÇ]A|COMPONENTE)\s*[-–—]\s*','',v); v=re.sub(r'^SOLDA\s+','',v).strip(); return v or 'NÃO INFORMADO'
def regiao(anom):
    a=strip_accents(txt(anom)).upper()
    for k,v in [('FECHAMENTO SUPERIOR','FECHAMENTO SUPERIOR'),('ESTR. TRASEIRA','ESTRUTURA TRASEIRA'),('ESTR TRASEIRA','ESTRUTURA TRASEIRA'),('LATERAL ESQUERDA','LATERAL ESQUERDA'),('LAT ESQ','LATERAL ESQUERDA'),('LATERAL DIREITA','LATERAL DIREITA'),('ASSOALHO','ASSOALHO'),('PISO','ASSOALHO/PISO'),('TETO','TETO'),('TRASEIRA','TRASEIRA'),('FRONTAL','FRONTAL'),('FRENTE','FRONTAL'),('INFERIOR','INFERIOR'),('PARALAMAS','PARALAMAS')]:
        if k in a: return v
    return 'NÃO CLASSIFICADO'
def familia(d1, anom):
    d=strip_accents((txt(d1) or txt(anom))).upper()
    if any(x in d for x in ['RESPING','CORDAO','FALTA CORDAO','POROSIDADE','FUSAO','SOLDA']): return 'SOLDA'
    if any(x in d for x in ['ACABAMENTO','OXIDADO','PINTURA']): return 'ACABAMENTO / SUPERFÍCIE'
    if any(x in d for x in ['FALTA COMPONENTE','PECA ERRADA','COMPONENTE FORA']): return 'COMPONENTE / MONTAGEM'
    if any(x in d for x in ['DESALINHADO','TORTO','FORA DE POSICAO']): return 'DIMENSIONAL / POSIÇÃO'
    if any(x in d for x in ['DANIFICADO','QUEBRADO','TRINCADO']): return 'DANO'
    return 'OUTROS'
def parse_dt(s):
    dt=pd.to_datetime(s,errors='coerce'); m=dt.isna() & s.notna()
    if m.any(): dt.loc[m]=pd.to_datetime(s[m],errors='coerce',dayfirst=True)
    return dt
def enrich(df):
    if df.empty: return df
    df=df.copy(); df['REGIAO_EXTRAIDA']=df['ANOMALIA_FALHA'].map(regiao); df['FAMILIA_DEFEITO']=df.apply(lambda r: familia(r.get('D1',''),r.get('ANOMALIA_FALHA','')),axis=1); df['SEMANA_INICIO']=df.DT_HR_INSPECAO.dt.to_period('W-MON').apply(lambda r: r.start_time.date()); return df

def read_upload(up):
    ext=up.name.lower().split('.')[-1]; data=up.getvalue()
    if ext=='csv':
        last=None
        for enc in ['utf-16','utf-8-sig','latin1']:
            for sep in ['\t',';',',',None]:
                try: return normalize_columns(pd.read_csv(io.BytesIO(data),encoding=enc,sep=sep,engine='python',dtype=str))
                except Exception as e: last=e
        raise ValueError(f'Não foi possível ler CSV: {last}')
    return normalize_columns(pd.read_excel(io.BytesIO(data),engine='openpyxl' if ext=='xlsx' else 'xlrd',dtype=str))
def prepare(raw):
    df=raw.copy(); miss=[c for c in REQ if c not in df.columns]
    if miss: raise ValueError('Colunas obrigatórias ausentes: '+', '.join(miss))
    for c in OPTIONAL:
        if c not in df.columns: df[c]=''
    df['CD_POSTO_CN']=df.CD_POSTO_CN.map(lambda x:'QG09' if 'QG09' in txt(x).upper() else txt(x).upper())
    df['CD_MODELO']=df.CD_MODELO.map(lambda x:txt(x).upper()); df['MODELO_CORRIGIDO']=df.CD_MODELO.map(corr_modelo); df['DT_HR_INSPECAO']=parse_dt(df.DT_HR_INSPECAO); df['ANOMALIA_FALHA']=df.ANOMALIA_FALHA.map(txt); df['D1']=df.D1.map(txt); df['D1_GERAL']=df.apply(lambda r: falha_geral(r.D1,r.ANOMALIA_FALHA),axis=1)
    for c in ['NR_WO','NR_SERIE','POSTO_ORIGEM_FALHA','C_AREA_ORIGEM_FALHA']: df[c]=df[c].map(txt)
    q=df[df.CD_POSTO_CN.eq(POSTO_FIXO)&df.DT_HR_INSPECAO.notna()].copy(); f=q[q.ANOMALIA_FALHA.ne('')].copy(); cols=['NR_WO','NR_SERIE','CD_MODELO','MODELO_CORRIGIDO','DT_HR_INSPECAO','ANOMALIA_FALHA','D1','D1_GERAL','POSTO_ORIGEM_FALHA','C_AREA_ORIGEM_FALHA']
    return df, enrich(q[cols]), enrich(f[cols])
def con(): return sqlite3.connect(DB,check_same_thread=False)
def init(c):
    c.execute('CREATE TABLE IF NOT EXISTS upload_log(id INTEGER PRIMARY KEY AUTOINCREMENT,file_name TEXT,uploaded_at TEXT,total_rows INTEGER,qg09_rows INTEGER,falhas_rows INTEGER,min_date TEXT,max_date TEXT,mode TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS falhas_qg09(id INTEGER PRIMARY KEY AUTOINCREMENT,upload_id INTEGER,nr_wo TEXT,nr_serie TEXT,cd_modelo TEXT,modelo_corrigido TEXT,dt_hr_inspecao TEXT,anomalia_falha TEXT,d1 TEXT,d1_geral TEXT,posto_origem_falha TEXT,c_area_origem_falha TEXT)'); c.commit()
def save(c,name,full,qg09,falhas,mode):
    mind=falhas.DT_HR_INSPECAO.dt.date.min().isoformat() if not falhas.empty else None; maxd=falhas.DT_HR_INSPECAO.dt.date.max().isoformat() if not falhas.empty else None
    uid=c.execute('INSERT INTO upload_log(file_name,uploaded_at,total_rows,qg09_rows,falhas_rows,min_date,max_date,mode) VALUES(?,?,?,?,?,?,?,?)',(name,datetime.now().isoformat(timespec='seconds'),len(full),len(qg09),len(falhas),mind,maxd,mode)).lastrowid
    rows=[(uid,r.NR_WO,r.NR_SERIE,r.CD_MODELO,r.MODELO_CORRIGIDO,r.DT_HR_INSPECAO.isoformat(sep=' ',timespec='seconds'),r.ANOMALIA_FALHA,r.D1,r.D1_GERAL,r.POSTO_ORIGEM_FALHA,r.C_AREA_ORIGEM_FALHA) for _,r in falhas.iterrows()]
    c.executemany('INSERT INTO falhas_qg09(upload_id,nr_wo,nr_serie,cd_modelo,modelo_corrigido,dt_hr_inspecao,anomalia_falha,d1,d1_geral,posto_origem_falha,c_area_origem_falha) VALUES(?,?,?,?,?,?,?,?,?,?,?)',rows); c.commit()
def load(c):
    df=pd.read_sql_query('SELECT nr_wo NR_WO,nr_serie NR_SERIE,cd_modelo CD_MODELO,modelo_corrigido MODELO_CORRIGIDO,dt_hr_inspecao DT_HR_INSPECAO,anomalia_falha ANOMALIA_FALHA,d1 D1,d1_geral D1_GERAL,posto_origem_falha POSTO_ORIGEM_FALHA,c_area_origem_falha C_AREA_ORIGEM_FALHA FROM falhas_qg09',c)
    if df.empty: return df
    df.DT_HR_INSPECAO=pd.to_datetime(df.DT_HR_INSPECAO,errors='coerce'); df.D1=df.D1.fillna(''); df.D1_GERAL=df.apply(lambda r: txt(r.D1_GERAL) or falha_geral(r.D1,r.ANOMALIA_FALHA),axis=1); return enrich(df.drop_duplicates())
def hist(c): return pd.read_sql_query('SELECT * FROM upload_log ORDER BY id DESC',c)
def clear(c): c.execute('DELETE FROM falhas_qg09'); c.execute('DELETE FROM upload_log'); c.commit()
def pareto(df,col,n=10):
    if df.empty or col not in df: return pd.DataFrame(columns=['Item','Quantidade','Percentual','Percentual Acumulado'])
    s=df[col].fillna('').astype(str).str.strip(); s=s[s.ne('')]
    out=s.value_counts().head(n).reset_index(); out.columns=['Item','Quantidade']; total=out.Quantidade.sum(); out['Percentual']=out.Quantidade/total if total else 0; out['Percentual Acumulado']=out.Percentual.cumsum(); return out
def kpi(l,v,s=''): return f"<div class='kpi'><div class='kpi-l'>{l}</div><div class='kpi-v'>{v}</div><div class='kpi-s'>{s}</div></div>"
def fmt_int(v): return f'{int(v):,}'.replace(',','.') if pd.notna(v) else '0'
def pct(v): return f'{float(v)*100:.1f}%'.replace('.',',')
def period(df,year,mode):
    ydf=df[df.DT_HR_INSPECAO.dt.year.eq(year)].copy(); mn,mx=ydf.DT_HR_INSPECAO.dt.date.min(),ydf.DT_HR_INSPECAO.dt.date.max()
    if mode=='Diário': d=st.sidebar.date_input('Dia',value=mx,min_value=mn,max_value=mx,format='DD/MM/YYYY'); return ydf,d,d,d.strftime('%d/%m/%Y')
    if mode=='Mensal': months=sorted(ydf.DT_HR_INSPECAO.dt.month.unique()); labels=[f'{m:02d}/{year}' for m in months]; lab=st.sidebar.selectbox('Mês',labels,index=len(labels)-1); m=int(lab[:2]); return ydf,date(year,m,1),date(year,m,monthrange(year,m)[1]),lab
    if mode=='Anual YTD': return ydf,date(year,1,1),mx,f'YTD {year} até {mx.strftime("%d/%m/%Y")}'
    p=st.sidebar.date_input('Período personalizado',value=(mn,mx),min_value=mn,max_value=mx,format='DD/MM/YYYY')
    if isinstance(p,tuple) and len(p)==2: return ydf,p[0],p[1],f'Personalizado {p[0].strftime("%d/%m/%Y")} a {p[1].strftime("%d/%m/%Y")}'
    return ydf,mn,mx,'Personalizado'
def week_table(df):
    if df.empty: return pd.DataFrame(columns=['D1_GERAL','SEMANA_INICIO','Quantidade'])
    return df.groupby(['D1_GERAL','SEMANA_INICIO']).size().reset_index(name='Quantidade').sort_values(['D1_GERAL','SEMANA_INICIO'])
def criticidade(df):
    wk=week_table(df); rows=[]
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
def alertas(df):
    rows=[]; wk=week_table(df)
    for falha,g in wk.groupby('D1_GERAL'):
        g=g.sort_values('SEMANA_INICIO')
        if len(g)<3: continue
        atual=float(g.Quantidade.iloc[-1]); media=float(g.Quantidade.iloc[:-1].tail(4).mean())
        if media and atual>=media*1.4: rows.append([falha,int(atual),round(media,1),round((atual-media)/media*100,1)])
    return pd.DataFrame(rows,columns=['Falha','Semana atual','Média últimas semanas','Aumento %']).sort_values('Aumento %',ascending=False)
def foco(df,crit):
    if df.empty: return pd.DataFrame(columns=['Prioridade','Modelo','Região','Falha','Quantidade','Criticidade'])
    ultima=df.SEMANA_INICIO.max(); base=df[df.SEMANA_INICIO.eq(ultima)]
    combo=base.groupby(['MODELO_CORRIGIDO','REGIAO_EXTRAIDA','D1_GERAL']).size().reset_index(name='Quantidade').sort_values('Quantidade',ascending=False).head(15)
    cmap=dict(zip(crit.Falha,crit.Criticidade)) if not crit.empty else {}
    combo['Criticidade']=combo.D1_GERAL.map(cmap).fillna('')
    combo.insert(0,'Prioridade',range(1,len(combo)+1))
    return combo.rename(columns={'MODELO_CORRIGIDO':'Modelo','REGIAO_EXTRAIDA':'Região','D1_GERAL':'Falha'})
def mensal(df):
    if df.empty: return pd.DataFrame(),pd.DataFrame()
    d=df.copy(); d['MES']=d.DT_HR_INSPECAO.dt.to_period('M').astype(str); meses=sorted(d.MES.unique())
    if len(meses)<2: return pd.DataFrame(),pd.DataFrame()
    ant,atu=meses[-2],meses[-1]
    resumo=pd.DataFrame([['Mês anterior',ant,len(d[d.MES.eq(ant)])],['Mês atual',atu,len(d[d.MES.eq(atu)])]],columns=['Período','Mês','Quantidade'])
    a=d[d.MES.eq(ant)].D1_GERAL.value_counts(); b=d[d.MES.eq(atu)].D1_GERAL.value_counts(); comp=pd.concat([a,b],axis=1).fillna(0); comp.columns=['Mês anterior','Mês atual']; comp['Diferença']=comp['Mês atual']-comp['Mês anterior']; comp['Variação %']=comp.apply(lambda r:(r.Diferença/r['Mês anterior']*100) if r['Mês anterior'] else 100,axis=1)
    return resumo,comp.reset_index().rename(columns={'index':'Falha'}).sort_values('Diferença',ascending=False)

c=con(); init(c)
st.markdown(f"<div class='head'>{logo_html()}<div><h1 style='margin:0;color:white'>Pareto de Falhas QG09</h1><p style='color:#B7BDC6'>Versão {APP_VERSION}: inteligência de criticidade, estabilidade, alertas, foco e comparativo mensal.</p><span class='badge'>Criticidade</span><span class='badge'>Estabilidade</span><span class='badge'>Alertas</span><span class='badge'>Foco</span><span class='badge'>Mensal</span></div></div>",unsafe_allow_html=True)
df_all=load(c)
tab_names=['Dashboard','Estratificar TOP','Região/Estrutura','Matriz','Tendência','Famílias','Criticidade/Estabilidade']
if FEATURE_LEVEL>=19: tab_names+=['Alertas/Foco']
if FEATURE_LEVEL>=20: tab_names+=['Comparativo Mensal']
tab_names+=['Upload','Histórico']
tabs=st.tabs(tab_names)
with st.sidebar:
    top_n=st.slider('Top N',5,25,10)
    if not df_all.empty:
        years=sorted(df_all.DT_HR_INSPECAO.dt.year.dropna().astype(int).unique()); year=st.selectbox('Ano',years,index=len(years)-1); mode=st.radio('Modo calendário',['Diário','Mensal','Anual YTD','Personalizado'])
    else: year=None; mode='Personalizado'
idx_upload=len(tab_names)-2; idx_hist=len(tab_names)-1
with tabs[idx_upload]:
    st.markdown("<div class='panel'><b>Upload</b><br>Use Somar ao calendário para manter mais de um ano.</div>",unsafe_allow_html=True)
    imode=st.radio('Modo de importação',['Somar ao calendário'],horizontal=True)
    up=st.file_uploader('Base (.csv, .xlsx ou .xls)',type=['csv','xlsx','xls'])
    if up:
        try:
            raw,orig,final=read_upload(up); full,qg09,falhas=prepare(raw); st.success(f'Arquivo lido: {up.name} | Linhas: {len(full)} | QG09: {len(qg09)} | Falhas QG09: {len(falhas)}')
            st.dataframe(falhas.head(200),use_container_width=True,hide_index=True)
            if st.button('Salvar no calendário',type='primary') and not falhas.empty: save(c,up.name,full,qg09,falhas,imode); st.rerun()
        except Exception as e: st.error(str(e))
df_all=load(c)
if df_all.empty or year is None:
    for i in range(len(tab_names)-2):
        with tabs[i]: st.info('Faça upload da base.')
else:
    ydf,start,end,label=period(df_all,year,mode); modelos=sorted(df_all.MODELO_CORRIGIDO.dropna().unique()); origens=sorted(df_all.POSTO_ORIGEM_FALHA.dropna().unique())
    st.sidebar.divider(); ms=st.sidebar.multiselect('Modelo',modelos); osel=st.sidebar.multiselect('Origem',origens)
    filt=ydf[(ydf.DT_HR_INSPECAO>=datetime.combine(start,time(0,0)))&(ydf.DT_HR_INSPECAO<=datetime.combine(end,time(23,59,59)))].copy()
    if ms: filt=filt[filt.MODELO_CORRIGIDO.isin(ms)]
    if osel: filt=filt[filt.POSTO_ORIGEM_FALHA.isin(osel)]
    pg=pareto(filt,'D1_GERAL',top_n); crit=criticidade(filt)
    with tabs[0]:
        a,b,cx,d=st.columns(4); a.markdown(kpi('Falhas',fmt_int(len(filt))),unsafe_allow_html=True); b.markdown(kpi('Top 1',pg.iloc[0].Item if not pg.empty else '-'),unsafe_allow_html=True); cx.markdown(kpi('Modelos',fmt_int(filt.MODELO_CORRIGIDO.nunique())),unsafe_allow_html=True); d.markdown(kpi('Regiões',fmt_int(filt.REGIAO_EXTRAIDA.nunique())),unsafe_allow_html=True)
        st.bar_chart(pg.set_index('Item')['Quantidade'] if not pg.empty else pd.Series(dtype=int)); show=pg.copy(); show['Percentual']=show.Percentual.map(pct); show['Percentual Acumulado']=show['Percentual Acumulado'].map(pct); st.dataframe(show,use_container_width=True,hide_index=True)
    with tabs[1]:
        if pg.empty: st.info('Sem dados.')
        else:
            opts=[f'TOP {i+1} - {r.Item} ({r.Quantidade})' for i,r in pg.reset_index(drop=True).iterrows()]; lab=st.selectbox('Escolha o TOP para estratificar',opts); top=pg.iloc[opts.index(lab)].Item; st.dataframe(filt[filt.D1_GERAL.eq(top)][['DT_HR_INSPECAO','MODELO_CORRIGIDO','REGIAO_EXTRAIDA','FAMILIA_DEFEITO','ANOMALIA_FALHA']],use_container_width=True,hide_index=True)
    with tabs[2]: st.bar_chart(pareto(filt,'REGIAO_EXTRAIDA',top_n).set_index('Item')['Quantidade'])
    with tabs[3]:
        topf=filt.D1_GERAL.value_counts().head(15).index.tolist(); mat=pd.pivot_table(filt[filt.D1_GERAL.isin(topf)],index='MODELO_CORRIGIDO',columns='D1_GERAL',values='ANOMALIA_FALHA',aggfunc='count',fill_value=0); st.dataframe(mat,use_container_width=True)
    with tabs[4]:
        falha=st.selectbox('Falha geral', sorted(filt.D1_GERAL.dropna().unique()) if not filt.empty else []); dt=filt[filt.D1_GERAL.eq(falha)].groupby('SEMANA_INICIO').size().reset_index(name='Quantidade'); st.line_chart(dt.set_index('SEMANA_INICIO')['Quantidade'] if not dt.empty else pd.Series(dtype=int)); st.dataframe(dt,use_container_width=True,hide_index=True)
    with tabs[5]: st.bar_chart(pareto(filt,'FAMILIA_DEFEITO',top_n).set_index('Item')['Quantidade'])
    with tabs[6]:
        st.markdown("<div class='panel'><b>Índice de criticidade + controle de estabilidade</b><br>Score baseado em volume, modelos afetados, regiões afetadas e tendência semanal.</div>",unsafe_allow_html=True); st.dataframe(crit,use_container_width=True,hide_index=True); st.bar_chart(crit.head(10).set_index('Falha')['Score criticidade'] if not crit.empty else pd.Series(dtype=float))
    pos=7
    if FEATURE_LEVEL>=19:
        with tabs[pos]:
            st.markdown("<div class='panel'><b>Alertas automáticos + foco da semana</b></div>",unsafe_allow_html=True); st.subheader('Alertas de aumento anormal'); st.dataframe(alertas(filt),use_container_width=True,hide_index=True); st.subheader('Foco recomendado da semana'); st.dataframe(foco(filt,crit),use_container_width=True,hide_index=True)
        pos+=1
    if FEATURE_LEVEL>=20:
        with tabs[pos]:
            st.markdown("<div class='panel'><b>Comparação mês atual x mês anterior</b></div>",unsafe_allow_html=True); r,c=mensal(filt)
            if r.empty: st.info('É necessário ter pelo menos dois meses no recorte.')
            else: st.dataframe(r,use_container_width=True,hide_index=True); st.bar_chart(r.set_index('Período')['Quantidade']); cc=c.copy(); cc['Variação %']=cc['Variação %'].map(lambda x:f'{x:.1f}%'.replace('.',',')); st.dataframe(cc,use_container_width=True,hide_index=True)
    with tabs[idx_hist]:
        st.dataframe(hist(c),use_container_width=True,hide_index=True)
        if st.button('Limpar calendário inteiro'): clear(c); st.rerun()
