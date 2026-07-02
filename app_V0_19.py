
import io, os, re, sqlite3, base64, unicodedata, html
from datetime import datetime, date, time, timedelta
from calendar import monthrange
import pandas as pd
import streamlit as st

st.set_page_config(page_title="AGCO | Pareto QG09 V0.19", page_icon="📊", layout="wide")
APP_VERSION="V0.19"
DB="pareto_qg09_v019.db"
MAPA={"VTBAGFC":"VTBA","V2MFGFC":"V2 MF","V2VTGFC":"V2 VT","G7GFCAN":"G7","G8GFCAN":"G8"}
REQ=["CD_POSTO_CN","CD_MODELO","DT_HR_INSPECAO","ANOMALIA_FALHA"]
ALIASES={"CD_POSTO_CN":["CD_POSTO_CN","CD_POSTO_FALHA","POSTO"],"CD_MODELO":["CD_MODELO","MODELO"],"DT_HR_INSPECAO":["DT_HR_INSPECAO","DT_CRIACAO_FALHA","DT_ENC_CERTIFICADO","DATA"],"ANOMALIA_FALHA":["ANOMALIA_FALHA","FALHA","ANOMALIA"],"D1":["D1"],"NR_WO":["NR_WO","WO"],"NR_SERIE":["NR_SERIE","SERIE"],"POSTO_ORIGEM_FALHA":["POSTO_ORIGEM_FALHA","ORIGEM"],"C_AREA_ORIGEM_FALHA":["C_AREA_ORIGEM_FALHA","AREA_ORIGEM_FALHA"]}
st.markdown("""<style>.stApp{background:#101113;color:#f4f5f7}[data-testid="stSidebar"]{background:#241F20;border-right:5px solid #C00031}.box{background:#181A1D;border-left:5px solid #C00031;border-radius:10px;padding:14px;margin:10px 0}.kpi{background:#202327;border-top:4px solid #C00031;border-radius:10px;padding:14px}.kpi b{font-size:1.4rem}.pareto{background:white;border-radius:10px;padding:10px;overflow-x:auto}</style>""", unsafe_allow_html=True)

def strip_accents(t): return ''.join(ch for ch in unicodedata.normalize('NFKD',str(t)) if not unicodedata.combining(ch))
def clean_col(c):
    t=strip_accents(str(c)).upper(); t=re.sub(r'[^A-Z0-9]+','_',t); return re.sub(r'_+','_',t).strip('_')
def txt(v): return '' if pd.isna(v) else re.sub(r'\s+',' ',str(v).strip())
def norm(df):
    df=df.copy(); orig=list(df.columns); df.columns=[clean_col(c) for c in df.columns]; ren={}; ex=set(df.columns)
    for can, als in ALIASES.items():
        if can in ex: continue
        for a in als:
            ca=clean_col(a)
            if ca in ex: ren[ca]=can; break
    if ren: df=df.rename(columns=ren)
    return df.loc[:,~df.columns.duplicated()].copy(),orig,list(df.columns)
def modelo(v):
    c=txt(v).upper(); return MAPA.get(c,c or 'Não informado')
def d1geral(d1,anom):
    v=(txt(d1) or txt(anom)).upper(); v=re.sub(r'^(SOLDA|PE[CÇ]A|COMPONENTE)\s*[-–—]\s*','',v); v=re.sub(r'^SOLDA\s+','',v).strip(); return v or 'NÃO INFORMADO'
def regiao(anom):
    a=strip_accents(txt(anom)).upper()
    for k,v in [('FECHAMENTO SUPERIOR','FECHAMENTO SUPERIOR'),('ESTR. TRASEIRA','ESTRUTURA TRASEIRA'),('ESTR TRASEIRA','ESTRUTURA TRASEIRA'),('LATERAL ESQUERDA','LATERAL ESQUERDA'),('LATERAL DIREITA','LATERAL DIREITA'),('ASSOALHO','ASSOALHO'),('PISO','ASSOALHO/PISO'),('TETO','TETO'),('TRASEIRA','TRASEIRA'),('FRONTAL','FRONTAL'),('FRENTE','FRONTAL'),('PARALAMAS','PARALAMAS')]:
        if k in a: return v
    return 'NÃO CLASSIFICADO'
def familia(d1,anom):
    d=strip_accents((txt(d1) or txt(anom))).upper()
    if any(x in d for x in ['RESPING','CORDAO','FALTA CORDAO','POROSIDADE','FUSAO','SOLDA']): return 'SOLDA'
    if any(x in d for x in ['ACABAMENTO','OXIDADO','PINTURA']): return 'ACABAMENTO / SUPERFÍCIE'
    if any(x in d for x in ['COMPONENTE','PECA ERRADA']): return 'COMPONENTE / MONTAGEM'
    if any(x in d for x in ['DESALINHADO','TORTO','FORA DE POSICAO']): return 'DIMENSIONAL / POSIÇÃO'
    return 'OUTROS'
def parse_dt(s):
    dt=pd.to_datetime(s,errors='coerce'); m=dt.isna() & s.notna()
    if m.any(): dt.loc[m]=pd.to_datetime(s[m],errors='coerce',dayfirst=True)
    return dt
def enrich(df):
    if df.empty: return df
    df=df.copy(); df['REGIAO_EXTRAIDA']=df.ANOMALIA_FALHA.map(regiao); df['FAMILIA_DEFEITO']=df.apply(lambda r: familia(r.get('D1',''),r.get('ANOMALIA_FALHA','')),axis=1); df['SEMANA_INICIO']=df.DT_HR_INSPECAO.dt.to_period('W-MON').apply(lambda r: r.start_time.date() if pd.notna(r.start_time) else None); return df

def read_file(up):
    ext=up.name.lower().split('.')[-1]; data=up.getvalue()
    if ext=='csv':
        for enc in ['utf-16','utf-8-sig','latin1']:
            for sep in ['	',';',',',None]:
                try: return norm(pd.read_csv(io.BytesIO(data),encoding=enc,sep=sep,engine='python',dtype=str))
                except: pass
        raise ValueError('Não foi possível ler CSV')
    return norm(pd.read_excel(io.BytesIO(data),engine='openpyxl' if ext=='xlsx' else 'xlrd',dtype=str))
def prepare(raw):
    df=raw.copy(); miss=[c for c in REQ if c not in df]
    if miss: raise ValueError('Colunas obrigatórias ausentes: '+', '.join(miss))
    for c in ['D1','NR_WO','NR_SERIE','POSTO_ORIGEM_FALHA','C_AREA_ORIGEM_FALHA']:
        if c not in df: df[c]=''
    df['CD_POSTO_CN']=df.CD_POSTO_CN.map(lambda x:'QG09' if 'QG09' in txt(x).upper() else txt(x).upper())
    df['CD_MODELO']=df.CD_MODELO.map(lambda x:txt(x).upper()); df['MODELO_CORRIGIDO']=df.CD_MODELO.map(modelo); df['DT_HR_INSPECAO']=parse_dt(df.DT_HR_INSPECAO); df['ANOMALIA_FALHA']=df.ANOMALIA_FALHA.map(txt); df['D1']=df.D1.map(txt); df['D1_GERAL']=df.apply(lambda r:d1geral(r.D1,r.ANOMALIA_FALHA),axis=1)
    q=df[df.CD_POSTO_CN.eq('QG09')&df.DT_HR_INSPECAO.notna()].copy(); f=q[q.ANOMALIA_FALHA.ne('')].copy(); cols=['NR_WO','NR_SERIE','CD_MODELO','MODELO_CORRIGIDO','DT_HR_INSPECAO','ANOMALIA_FALHA','D1','D1_GERAL','POSTO_ORIGEM_FALHA','C_AREA_ORIGEM_FALHA']
    return df,enrich(q[cols]),enrich(f[cols])
def con(): return sqlite3.connect(DB,check_same_thread=False)
def init(c):
    c.execute('CREATE TABLE IF NOT EXISTS falhas_qg09(id INTEGER PRIMARY KEY AUTOINCREMENT,nr_wo TEXT,nr_serie TEXT,cd_modelo TEXT,modelo_corrigido TEXT,dt_hr_inspecao TEXT,anomalia_falha TEXT,d1 TEXT,d1_geral TEXT,posto_origem_falha TEXT,c_area_origem_falha TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS upload_log(id INTEGER PRIMARY KEY AUTOINCREMENT,file_name TEXT,uploaded_at TEXT,total_rows INTEGER,qg09_rows INTEGER,falhas_rows INTEGER)'); c.commit()
def save(c,name,full,qg09,falhas):
    c.execute('INSERT INTO upload_log(file_name,uploaded_at,total_rows,qg09_rows,falhas_rows) VALUES(?,?,?,?,?)',(name,datetime.now().isoformat(timespec='seconds'),len(full),len(qg09),len(falhas)))
    rows=[(r.NR_WO,r.NR_SERIE,r.CD_MODELO,r.MODELO_CORRIGIDO,r.DT_HR_INSPECAO.isoformat(sep=' ',timespec='seconds'),r.ANOMALIA_FALHA,r.D1,r.D1_GERAL,r.POSTO_ORIGEM_FALHA,r.C_AREA_ORIGEM_FALHA) for _,r in falhas.iterrows()]
    c.executemany('INSERT INTO falhas_qg09(nr_wo,nr_serie,cd_modelo,modelo_corrigido,dt_hr_inspecao,anomalia_falha,d1,d1_geral,posto_origem_falha,c_area_origem_falha) VALUES(?,?,?,?,?,?,?,?,?,?)',rows); c.commit()
def load(c):
    df=pd.read_sql_query('SELECT nr_wo NR_WO,nr_serie NR_SERIE,cd_modelo CD_MODELO,modelo_corrigido MODELO_CORRIGIDO,dt_hr_inspecao DT_HR_INSPECAO,anomalia_falha ANOMALIA_FALHA,d1 D1,d1_geral D1_GERAL,posto_origem_falha POSTO_ORIGEM_FALHA,c_area_origem_falha C_AREA_ORIGEM_FALHA FROM falhas_qg09',c)
    if df.empty: return df
    df.DT_HR_INSPECAO=pd.to_datetime(df.DT_HR_INSPECAO,errors='coerce'); df.D1=df.D1.fillna(''); return enrich(df.drop_duplicates())
def pareto(df,col,n=10):
    if df.empty or col not in df: return pd.DataFrame(columns=['Item','Quantidade','Percentual','Percentual Acumulado'])
    s=df[col].fillna('').astype(str).str.strip(); s=s[s.ne('')]
    out=s.value_counts().head(n).reset_index(); out.columns=['Item','Quantidade']; total=out.Quantidade.sum(); out['Percentual']=out.Quantidade/total if total else 0; out['Percentual Acumulado']=out.Percentual.cumsum(); return out
def pct(v): return f'{float(v)*100:.1f}%'.replace('.',',')
def kpi(label,val,sub=''): st.markdown(f"<div class='kpi'><div>{label}</div><b>{val}</b><div>{sub}</div></div>",unsafe_allow_html=True)
def show_pareto(p,title):
    st.markdown(f"### {title}")
    st.bar_chart(p.set_index('Item')['Quantidade'] if not p.empty else pd.Series(dtype=float))
    out=p.copy()
    if not out.empty: out['Percentual']=out.Percentual.map(pct); out['Percentual Acumulado']=out['Percentual Acumulado'].map(pct)
    st.dataframe(out,use_container_width=True,hide_index=True)
def period(df,year,mode):
    ydf=df[df.DT_HR_INSPECAO.dt.year.eq(year)].copy(); mn,mx=ydf.DT_HR_INSPECAO.dt.date.min(),ydf.DT_HR_INSPECAO.dt.date.max()
    if mode=='Diário': d=st.sidebar.date_input('Dia',value=mx,min_value=mn,max_value=mx,format='DD/MM/YYYY'); return ydf,d,d,d.strftime('%d/%m/%Y')
    if mode=='Semanal':
        mondays=sorted({d-timedelta(days=d.weekday()) for d in ydf.DT_HR_INSPECAO.dt.date.dropna().unique()}); labels=[f"Semana {i+1:02d} - {m.strftime('%d/%m/%Y')} a {(m+timedelta(days=6)).strftime('%d/%m/%Y')}" for i,m in enumerate(mondays)]; lab=st.sidebar.selectbox('Semana',labels,index=len(labels)-1); m=mondays[labels.index(lab)]; return ydf,m,m+timedelta(days=6),lab
    if mode=='Mensal': months=sorted(ydf.DT_HR_INSPECAO.dt.month.unique()); labels=[f'{m:02d}/{year}' for m in months]; lab=st.sidebar.selectbox('Mês',labels,index=len(labels)-1); m=int(lab[:2]); return ydf,date(year,m,1),date(year,m,monthrange(year,m)[1]),lab
    if mode=='Anual YTD': return ydf,date(year,1,1),mx,f'YTD {year}'
    p=st.sidebar.date_input('Período personalizado',value=(mn,mx),min_value=mn,max_value=mx,format='DD/MM/YYYY')
    if isinstance(p,tuple) and len(p)==2: return ydf,p[0],p[1],'Personalizado'
    return ydf,mn,mx,'Personalizado'
def criticidade(df):
    if df.empty: return pd.DataFrame(columns=['Falha','Quantidade','Modelos afetados','Regiões afetadas','Tendência %','Estabilidade','Score criticidade','Criticidade'])
    wk=df.groupby(['D1_GERAL','SEMANA_INICIO']).size().reset_index(name='Quantidade').sort_values(['D1_GERAL','SEMANA_INICIO']); rows=[]
    for falha,g in wk.groupby('D1_GERAL'):
        dff=df[df.D1_GERAL.eq(falha)]; qtd=int(g.Quantidade.sum()); modelos=dff.MODELO_CORRIGIDO.nunique(); regs=dff.REGIAO_EXTRAIDA.nunique()
        if len(g)<3: status='Sem histórico suficiente'; trend=0
        else:
            ult=g.Quantidade.tail(2).mean(); ant=g.Quantidade.head(max(len(g)-2,1)).mean(); trend=((ult-ant)/ant*100) if ant else 0
            status='Em crescimento' if trend>=25 else 'Em queda' if trend<=-25 else 'Instável' if g.Quantidade.std()>g.Quantidade.mean()*0.7 else 'Estável'
        score=qtd+modelos*8+regs*5+max(trend,0)*1.5; cls='Crítica' if score>=120 else 'Alta' if score>=70 else 'Média' if score>=30 else 'Baixa'
        rows.append([falha,qtd,modelos,regs,round(trend,1),status,round(score,1),cls])
    return pd.DataFrame(rows,columns=['Falha','Quantidade','Modelos afetados','Regiões afetadas','Tendência %','Estabilidade','Score criticidade','Criticidade']).sort_values('Score criticidade',ascending=False)
def alertas(df):
    wk=df.groupby(['D1_GERAL','SEMANA_INICIO']).size().reset_index(name='Quantidade').sort_values(['D1_GERAL','SEMANA_INICIO']); rows=[]
    for falha,g in wk.groupby('D1_GERAL'):
        if len(g)<3: continue
        atual=g.Quantidade.iloc[-1]; media=g.Quantidade.iloc[:-1].tail(4).mean()
        if media and atual>=media*1.4: rows.append([falha,int(atual),round(media,1),round((atual-media)/media*100,1)])
    return pd.DataFrame(rows,columns=['Falha','Semana atual','Média últimas semanas','Aumento %']).sort_values('Aumento %',ascending=False)
def foco(df,crit):
    if df.empty: return pd.DataFrame()
    ultima=df.SEMANA_INICIO.max(); base=df[df.SEMANA_INICIO.eq(ultima)]; combo=base.groupby(['MODELO_CORRIGIDO','REGIAO_EXTRAIDA','D1_GERAL']).size().reset_index(name='Quantidade').sort_values('Quantidade',ascending=False).head(10); combo.insert(0,'Prioridade',range(1,len(combo)+1)); return combo.rename(columns={'MODELO_CORRIGIDO':'Modelo','REGIAO_EXTRAIDA':'Região','D1_GERAL':'Falha'})

c=con(); init(c)
st.title('Pareto de Falhas QG09 - V0.19')
st.caption('Semanal corrigido + estabilidade detalhada + alertas/foco no Dashboard')
df_all=load(c)
tabs=st.tabs(['Dashboard','Estratificar TOP','Região/Estrutura','Matriz Modelo x Falha','Tendência Semanal','Criticidade/Estabilidade','Upload','Histórico'])
with st.sidebar:
    top_n=st.slider('Top N',5,25,10)
    if not df_all.empty:
        years=sorted(df_all.DT_HR_INSPECAO.dt.year.dropna().astype(int).unique()); year=st.selectbox('Ano',years,index=len(years)-1); mode=st.radio('Modo calendário',['Diário','Semanal','Mensal','Anual YTD','Personalizado'])
    else: year=None; mode='Personalizado'
with tabs[6]:
    up=st.file_uploader('Base (.csv, .xlsx ou .xls)',type=['csv','xlsx','xls'])
    if up:
        try:
            raw,orig,final=read_file(up); full,qg09,falhas=prepare(raw); st.success(f'Arquivo lido: {up.name} | QG09: {len(qg09)} | Falhas: {len(falhas)}'); st.dataframe(falhas.head(200),use_container_width=True,hide_index=True)
            if st.button('Salvar no calendário',type='primary') and not falhas.empty: save(c,up.name,full,qg09,falhas); st.rerun()
        except Exception as e: st.error(str(e))
df_all=load(c)
if df_all.empty or year is None:
    for i in range(6):
        with tabs[i]: st.info('Faça upload da base.')
else:
    ydf,start,end,label=period(df_all,year,mode); filt=ydf[(ydf.DT_HR_INSPECAO>=datetime.combine(start,time(0,0)))&(ydf.DT_HR_INSPECAO<=datetime.combine(end,time(23,59,59)))].copy()
    crit=criticidade(filt); pg=pareto(filt,'D1_GERAL',top_n)
    with tabs[0]:
        c1,c2,c3,c4=st.columns(4); c1.metric('Falhas',len(filt)); c2.metric('Top 1',pg.iloc[0].Item if not pg.empty else '-'); c3.metric('Críticas',int((crit.Criticidade=='Crítica').sum()) if not crit.empty else 0); c4.metric('Em crescimento',int((crit.Estabilidade=='Em crescimento').sum()) if not crit.empty else 0)
        show_pareto(pg,f'Pareto Falha Geral - {label}')
        a,b=st.columns(2)
        with a: st.markdown('<div class="box"><b>Alertas automáticos</b><br>Falhas com aumento acima de 40% contra a média das últimas semanas.</div>',unsafe_allow_html=True); st.dataframe(alertas(filt),use_container_width=True,hide_index=True)
        with b: st.markdown('<div class="box"><b>Foco recomendado da semana</b><br>Modelo + Região + Falha com maior volume na última semana.</div>',unsafe_allow_html=True); st.dataframe(foco(filt,crit),use_container_width=True,hide_index=True)
    with tabs[1]:
        if pg.empty: st.info('Sem dados.')
        else:
            opts=[f'TOP {i+1} - {r.Item} ({r.Quantidade})' for i,r in pg.reset_index(drop=True).iterrows()]; lab=st.selectbox('TOP',opts); top=pg.iloc[opts.index(lab)].Item; df_top=filt[filt.D1_GERAL.eq(top)]; show_pareto(pareto(df_top,'MODELO_CORRIGIDO',25),'Distribuição por modelo'); st.dataframe(df_top,use_container_width=True,hide_index=True)
    with tabs[2]: show_pareto(pareto(filt,'REGIAO_EXTRAIDA',top_n),f'Pareto por Região - {label}')
    with tabs[3]:
        topf=filt.D1_GERAL.value_counts().head(15).index.tolist(); mat=pd.pivot_table(filt[filt.D1_GERAL.isin(topf)],index='MODELO_CORRIGIDO',columns='D1_GERAL',values='ANOMALIA_FALHA',aggfunc='count',fill_value=0); st.dataframe(mat,use_container_width=True)
    with tabs[4]:
        fal=st.selectbox('Falha geral',sorted(filt.D1_GERAL.dropna().unique())); d=filt[filt.D1_GERAL.eq(fal)].groupby('SEMANA_INICIO').size().reset_index(name='Quantidade'); st.line_chart(d.set_index('SEMANA_INICIO')['Quantidade']); st.dataframe(d,use_container_width=True,hide_index=True)
    with tabs[5]:
        st.markdown('<div class="box"><b>Criticidade e estabilidade</b><br>Use o filtro abaixo para saber exatamente quais falhas estão em queda, crescimento, instáveis, estáveis ou sem histórico.</div>',unsafe_allow_html=True)
        pscore=crit[['Falha','Score criticidade']].rename(columns={'Falha':'Item','Score criticidade':'Quantidade'}).head(15).copy(); total=pscore.Quantidade.sum(); pscore['Percentual']=pscore.Quantidade/total if total else 0; pscore['Percentual Acumulado']=pscore.Percentual.cumsum(); show_pareto(pscore,'Pareto clássico por score de criticidade')
        pest=pareto_from_series(crit.Estabilidade,10); show_pareto(pest,'Pareto clássico por status de estabilidade')
        status=st.selectbox('Ver falhas por status',['Todos']+sorted(crit.Estabilidade.dropna().unique()))
        detalhe=crit if status=='Todos' else crit[crit.Estabilidade.eq(status)]
        st.dataframe(detalhe,use_container_width=True,hide_index=True)
with tabs[7]:
    st.dataframe(pd.read_sql_query('SELECT * FROM upload_log ORDER BY id DESC',c),use_container_width=True,hide_index=True)
    if st.button('Limpar calendário inteiro'): c.execute('DELETE FROM falhas_qg09'); c.execute('DELETE FROM upload_log'); c.commit(); st.rerun()
