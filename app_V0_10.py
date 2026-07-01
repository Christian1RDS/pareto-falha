
import io, re, sqlite3, unicodedata, html
from datetime import datetime, date, time, timedelta
from calendar import monthrange
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Pareto QG09 V0.10", page_icon="📊", layout="wide")
APP_VERSION = "V0.10"
DB = "pareto_qg09_v010.db"
POSTO_FIXO = "QG09"

MAPA_MODELOS = {"VTBAGFC":"VTBA", "V2MFGFC":"V2 MF", "V2VTGFC":"V2 VT", "G7GFCAN":"G7", "G8GFCAN":"G8"}
ALIASES = {
    "CD_POSTO_CN": ["CD_POSTO_CN", "CD_POSTO_FALHA", "POSTO", "POSTO_CN", "CD_POSTO"],
    "CD_MODELO": ["CD_MODELO", "MODELO", "COD_MODELO"],
    "DT_HR_INSPECAO": ["DT_HR_INSPECAO", "DT_CRIACAO_FALHA", "DT_ENC_CERTIFICADO", "DT_ENCERRAMENTO_FALHA", "DATA_INSPECAO", "DATA"],
    "ANOMALIA_FALHA": ["ANOMALIA_FALHA", "FALHA", "ANOMALIA", "DESCRICAO_FALHA"],
    "D1": ["D1"],
    "NR_WO": ["NR_WO", "WO", "ORDEM"],
    "NR_SERIE": ["NR_SERIE", "SERIE", "CHASSI"],
    "POSTO_ORIGEM_FALHA": ["POSTO_ORIGEM_FALHA", "ORIGEM_FALHA", "POSTO_ORIGEM", "ORIGEM"],
    "C_AREA_ORIGEM_FALHA": ["C_AREA_ORIGEM_FALHA", "AREA_ORIGEM_FALHA", "AREA_ORIGEM"],
    "C_DPU_QG_AMARELO": ["C_DPU_QG_AMARELO", "DPU", "DPU_QG_AMARELO"],
}
REQ = ["CD_POSTO_CN", "CD_MODELO", "DT_HR_INSPECAO", "ANOMALIA_FALHA"]
OPTIONAL = ["D1", "NR_WO", "NR_SERIE", "POSTO_ORIGEM_FALHA", "C_AREA_ORIGEM_FALHA", "C_DPU_QG_AMARELO"]

CSS = """
<style>
.stApp{background:radial-gradient(circle at top left,#1b2e54 0,#0b1324 42%,#08101f 100%);color:#e8eefc;}
[data-testid="stSidebar"]{background:linear-gradient(180deg,#0e1930 0%,#0a1222 100%);}
.block-container{padding-top:1.1rem}.hero{padding:24px 28px;border:1px solid rgba(255,255,255,.10);background:linear-gradient(135deg,rgba(47,128,237,.22),rgba(18,29,52,.94));border-radius:22px;box-shadow:0 18px 45px rgba(0,0,0,.25);margin-bottom:18px}.hero h1{margin:0;color:white}.hero p{color:#a9b8d4}.badge{display:inline-block;padding:5px 10px;border-radius:999px;border:1px solid rgba(255,255,255,.14);background:rgba(47,128,237,.14);color:#dce9ff;font-weight:700;font-size:.80rem;margin-right:6px;margin-top:8px}.panel{background:rgba(17,28,51,.88);border:1px solid rgba(255,255,255,.09);border-radius:20px;padding:18px;box-shadow:0 14px 30px rgba(0,0,0,.2);margin-bottom:16px}.kpi{background:linear-gradient(180deg,rgba(28,45,77,.95),rgba(18,29,52,.95));border:1px solid rgba(255,255,255,.10);border-radius:18px;padding:18px;min-height:115px}.kpi-label{color:#a9b8d4;font-size:.82rem;font-weight:800;text-transform:uppercase}.kpi-value{color:white;font-size:1.8rem;font-weight:900;margin-top:8px}.kpi-sub{color:#a9b8d4;font-size:.85rem}.pareto-box{background:#08101f;border:1px solid rgba(255,255,255,.10);border-radius:18px;padding:14px;overflow-x:auto}svg text{font-family:Arial,sans-serif}.small-note{color:#a9b8d4;font-size:.9rem}
</style>
"""

# ---------- utilidades ----------
def strip_accents(txt):
    return "".join(ch for ch in unicodedata.normalize("NFKD", str(txt)) if not unicodedata.combining(ch))

def clean_col_name(c):
    txt = str(c).replace("\\_", "_").replace("\\", "").strip()
    txt = strip_accents(txt).upper()
    txt = re.sub(r"[^A-Z0-9]+", "_", txt)
    return re.sub(r"_+", "_", txt).strip("_")

def normalize_columns(df):
    df = df.copy()
    original = list(df.columns)
    df.columns = [clean_col_name(c) for c in df.columns]
    existing = set(df.columns)
    ren = {}
    for canon, aliases in ALIASES.items():
        if canon in existing: continue
        for a in aliases:
            ca = clean_col_name(a)
            if ca in existing:
                ren[ca] = canon
                break
    if ren: df = df.rename(columns=ren)
    return df.loc[:, ~df.columns.duplicated()].copy(), original, list(df.columns)

def norm_text(v):
    if pd.isna(v): return ""
    return re.sub(r"\s+", " ", str(v).strip())

def norm_posto(v):
    t = norm_text(v).upper()
    return "QG09" if "QG09" in t else t

def falha_geral(d1, anomalia):
    val = norm_text(d1).upper() or norm_text(anomalia).upper()
    val = re.sub(r"^(SOLDA|PE[CÇ]A|COMPONENTE)\s*[-–—]\s*", "", val).strip()
    val = re.sub(r"^SOLDA\s+", "", val).strip()
    return val or "NÃO INFORMADO"

def corrige_modelo(v):
    code = norm_text(v).upper()
    return MAPA_MODELOS.get(code, code or "Não informado")

def parse_dt(s):
    dt = pd.to_datetime(s, errors="coerce")
    mask = dt.isna() & s.notna()
    if mask.any(): dt.loc[mask] = pd.to_datetime(s[mask], errors="coerce", dayfirst=True)
    return dt

def read_file(uploaded):
    ext = uploaded.name.lower().split(".")[-1]
    data = uploaded.getvalue()
    if ext == "csv":
        last = None
        for enc in ["utf-16", "utf-8-sig", "latin1"]:
            for sep in ["\t", ";", ",", None]:
                try:
                    raw = pd.read_csv(io.BytesIO(data), encoding=enc, sep=sep, engine="python", dtype=str)
                    return normalize_columns(raw)
                except Exception as e: last = e
        raise ValueError(f"Não foi possível ler CSV: {last}")
    engine = "openpyxl" if ext == "xlsx" else "xlrd"
    raw = pd.read_excel(io.BytesIO(data), engine=engine, dtype=str)
    return normalize_columns(raw)

def prepare(raw):
    df = raw.copy()
    missing = [c for c in REQ if c not in df.columns]
    if missing: raise ValueError("Colunas obrigatórias ausentes: " + ", ".join(missing))
    for c in OPTIONAL:
        if c not in df.columns: df[c] = ""
    df["CD_POSTO_CN"] = df["CD_POSTO_CN"].map(norm_posto)
    df["CD_MODELO"] = df["CD_MODELO"].map(lambda x: norm_text(x).upper())
    df["MODELO_CORRIGIDO"] = df["CD_MODELO"].map(corrige_modelo)
    df["DT_HR_INSPECAO"] = parse_dt(df["DT_HR_INSPECAO"])
    df["ANOMALIA_FALHA"] = df["ANOMALIA_FALHA"].map(norm_text)
    df["D1"] = df["D1"].map(norm_text)
    df["D1_GERAL"] = df.apply(lambda r: falha_geral(r["D1"], r["ANOMALIA_FALHA"]), axis=1)
    for c in ["NR_WO", "NR_SERIE", "POSTO_ORIGEM_FALHA", "C_AREA_ORIGEM_FALHA"]:
        df[c] = df[c].map(norm_text)
    qg09 = df[df["CD_POSTO_CN"].eq(POSTO_FIXO) & df["DT_HR_INSPECAO"].notna()].copy()
    falhas = qg09[qg09["ANOMALIA_FALHA"].ne("")].copy()
    cols = ["CD_POSTO_CN","NR_WO","NR_SERIE","CD_MODELO","MODELO_CORRIGIDO","DT_HR_INSPECAO","ANOMALIA_FALHA","D1","D1_GERAL","POSTO_ORIGEM_FALHA","C_AREA_ORIGEM_FALHA","C_DPU_QG_AMARELO"]
    return df, qg09[cols], falhas[cols]

# ---------- banco ----------
def conn(): return sqlite3.connect(DB, check_same_thread=False)

def init_db(c):
    c.execute("""CREATE TABLE IF NOT EXISTS upload_log(id INTEGER PRIMARY KEY AUTOINCREMENT,file_name TEXT,uploaded_at TEXT,total_rows INTEGER,qg09_rows INTEGER,falhas_rows INTEGER,min_date TEXT,max_date TEXT,mode TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS falhas_qg09(id INTEGER PRIMARY KEY AUTOINCREMENT,upload_id INTEGER,nr_wo TEXT,nr_serie TEXT,cd_modelo TEXT,modelo_corrigido TEXT,dt_hr_inspecao TEXT,anomalia_falha TEXT,d1 TEXT,d1_geral TEXT,posto_origem_falha TEXT,c_area_origem_falha TEXT)""")
    c.commit()

def delete_period(c, sdate, edate):
    s = datetime.combine(sdate, time(0,0)).isoformat(sep=" ")
    e = datetime.combine(edate, time(23,59,59)).isoformat(sep=" ")
    c.execute("DELETE FROM falhas_qg09 WHERE datetime(dt_hr_inspecao) BETWEEN datetime(?) AND datetime(?)", (s,e)); c.commit()

def delete_year(c, year):
    c.execute("DELETE FROM falhas_qg09 WHERE strftime('%Y', dt_hr_inspecao)=?", (str(year),)); c.commit()

def save_upload(c, file_name, full, qg09, falhas, mode):
    min_d = falhas["DT_HR_INSPECAO"].dt.date.min().isoformat() if not falhas.empty else None
    max_d = falhas["DT_HR_INSPECAO"].dt.date.max().isoformat() if not falhas.empty else None
    cur = c.execute("INSERT INTO upload_log(file_name,uploaded_at,total_rows,qg09_rows,falhas_rows,min_date,max_date,mode) VALUES(?,?,?,?,?,?,?,?)", (file_name, datetime.now().isoformat(timespec="seconds"), len(full), len(qg09), len(falhas), min_d, max_d, mode))
    uid = cur.lastrowid
    rows=[]
    for _,r in falhas.iterrows():
        rows.append((uid, r.NR_WO, r.NR_SERIE, r.CD_MODELO, r.MODELO_CORRIGIDO, r.DT_HR_INSPECAO.isoformat(sep=" ", timespec="seconds"), r.ANOMALIA_FALHA, r.D1, r.D1_GERAL, r.POSTO_ORIGEM_FALHA, r.C_AREA_ORIGEM_FALHA))
    c.executemany("INSERT INTO falhas_qg09(upload_id,nr_wo,nr_serie,cd_modelo,modelo_corrigido,dt_hr_inspecao,anomalia_falha,d1,d1_geral,posto_origem_falha,c_area_origem_falha) VALUES(?,?,?,?,?,?,?,?,?,?,?)", rows)
    c.commit(); return uid

def load_calendar(c):
    df = pd.read_sql_query("SELECT nr_wo NR_WO,nr_serie NR_SERIE,cd_modelo CD_MODELO,modelo_corrigido MODELO_CORRIGIDO,dt_hr_inspecao DT_HR_INSPECAO,anomalia_falha ANOMALIA_FALHA,d1 D1,d1_geral D1_GERAL,posto_origem_falha POSTO_ORIGEM_FALHA,c_area_origem_falha C_AREA_ORIGEM_FALHA FROM falhas_qg09", c)
    if df.empty: return df
    df["DT_HR_INSPECAO"] = pd.to_datetime(df["DT_HR_INSPECAO"], errors="coerce")
    df["D1"] = df["D1"].fillna("").astype(str)
    df["D1_GERAL"] = df.apply(lambda r: norm_text(r["D1_GERAL"]) or falha_geral(r["D1"], r["ANOMALIA_FALHA"]), axis=1)
    return df.drop_duplicates(subset=["NR_WO","NR_SERIE","CD_MODELO","DT_HR_INSPECAO","ANOMALIA_FALHA","POSTO_ORIGEM_FALHA"], keep="last")

def history(c): return pd.read_sql_query("SELECT * FROM upload_log ORDER BY id DESC", c)
def clear(c): c.execute("DELETE FROM falhas_qg09"); c.execute("DELETE FROM upload_log"); c.commit()

# ---------- período e pareto ----------
def fmt_int(v): return f"{int(v):,}".replace(",", ".") if pd.notna(v) else "0"
def fmt_pct(v): return f"{float(v)*100:.1f}%".replace(".", ",")

def make_pareto(df, col, top_n):
    if df.empty or col not in df: return pd.DataFrame(columns=["Item","Quantidade","Percentual","Percentual Acumulado"])
    s = df[col].fillna("").astype(str).str.strip(); s = s[s.ne("")]
    out = s.value_counts().head(top_n).reset_index(); out.columns=["Item","Quantidade"]
    total = out["Quantidade"].sum(); out["Percentual"] = out["Quantidade"]/total if total else 0; out["Percentual Acumulado"] = out["Percentual"].cumsum()
    return out

def kpi(label, value, sub=""):
    return f"<div class='kpi'><div class='kpi-label'>{html.escape(str(label))}</div><div class='kpi-value'>{html.escape(str(value))}</div><div class='kpi-sub'>{html.escape(str(sub))}</div></div>"

def simple_svg(p, title):
    if p.empty: return "<div class='pareto-box'>Sem dados.</div>"
    width,height,ml,mr,mt,mb=1180,520,70,40,55,145; pw=width-ml-mr; ph=height-mt-mb; mx=max(p["Quantidade"].max(),1); step=pw/max(len(p),1); bw=min(step*.68,72)
    parts=[f"<div class='pareto-box'><svg viewBox='0 0 {width} {height}' width='100%' height='{height}'>", "<rect width='100%' height='100%' fill='#08101f'/>", f"<text x='{ml}' y='32' fill='white' font-size='22' font-weight='800'>{html.escape(title)}</text>"]
    pts=[]
    for i,r in p.reset_index(drop=True).iterrows():
        x=ml+step*i+step/2; h=(r.Quantidade/mx)*ph; y=mt+ph-h; lab=str(r.Item); short=lab[:24]+('...' if len(lab)>24 else '')
        parts.append(f"<rect x='{x-bw/2:.1f}' y='{y:.1f}' width='{bw:.1f}' height='{h:.1f}' fill='#2f80ed' rx='4'><title>{html.escape(lab)} - {int(r.Quantidade)}</title></rect>")
        parts.append(f"<text x='{x:.1f}' y='{max(y-7,45):.1f}' fill='#e8eefc' font-size='12' text-anchor='middle'>{int(r.Quantidade)}</text>")
        parts.append(f"<text x='{x:.1f}' y='{mt+ph+23}' fill='#c8d5ef' font-size='11' text-anchor='end' transform='rotate(-35 {x:.1f} {mt+ph+23})'>{html.escape(short)}</text>")
        pts.append((x, mt+ph-r['Percentual Acumulado']*ph))
    parts.append("<polyline points='"+" ".join(f"{x:.1f},{y:.1f}" for x,y in pts)+"' fill='none' stroke='#ff3b30' stroke-width='3'/>")
    parts.append("</svg></div>"); return "".join(parts)

def period_filter(df, year, mode):
    ydf = df[df.DT_HR_INSPECAO.dt.year.eq(year)].copy()
    mn, mx = ydf.DT_HR_INSPECAO.dt.date.min(), ydf.DT_HR_INSPECAO.dt.date.max()
    if mode == "Diário":
        d = st.sidebar.date_input("Dia", value=mx, min_value=mn, max_value=mx, format="DD/MM/YYYY"); return ydf, d, d, d.strftime('%d/%m/%Y')
    if mode == "Mensal":
        months = sorted(ydf.DT_HR_INSPECAO.dt.month.unique()); labels=[f"{m:02d}/{year}" for m in months]; lab=st.sidebar.selectbox("Mês", labels, index=len(labels)-1); m=int(lab[:2]); return ydf, date(year,m,1), date(year,m,monthrange(year,m)[1]), lab
    if mode == "Semanal":
        dates=sorted(ydf.DT_HR_INSPECAO.dt.date.unique()); mondays=sorted({d-timedelta(days=d.weekday()) for d in dates}); labels=[f"Semana {i+1:02d} - {m.strftime('%d/%m/%Y')} a {(m+timedelta(days=6)).strftime('%d/%m/%Y')}" for i,m in enumerate(mondays)]; lab=st.sidebar.selectbox("Semana", labels, index=len(labels)-1); ix=labels.index(lab); return ydf, mondays[ix], mondays[ix]+timedelta(days=6), lab
    if mode == "Anual YTD": return ydf, date(year,1,1), mx, f"YTD {year} até {mx.strftime('%d/%m/%Y')}"
    p=st.sidebar.date_input("Período personalizado", value=(mn,mx), min_value=mn, max_value=mx, format="DD/MM/YYYY")
    if isinstance(p, tuple) and len(p)==2: return ydf, p[0], p[1], f"Personalizado {p[0].strftime('%d/%m/%Y')} a {p[1].strftime('%d/%m/%Y')}"
    return ydf, mn, mx, "Personalizado"

# ---------- UI ----------
c=conn(); init_db(c)
st.markdown(CSS, unsafe_allow_html=True)
st.markdown(f"<div class='hero'><h1>Pareto de Falhas QG09</h1><p>Versão {APP_VERSION}: opção Todos no detalhamento do TOP e ranking geral da falha completa.</p><span class='badge'>D1_GERAL</span><span class='badge'>Todos</span><span class='badge'>Ranking completo</span><span class='badge'>QG09 fixo</span></div>", unsafe_allow_html=True)

df_all=load_calendar(c)
tabs=st.tabs(["Dashboard", "Estratificar TOP", "Upload", "Histórico"])

with st.sidebar:
    top_n=st.slider("Top N",5,25,10)
    if not df_all.empty:
        years=sorted(df_all.DT_HR_INSPECAO.dt.year.dropna().astype(int).unique())
        year=st.selectbox("Ano", years, index=len(years)-1)
        mode=st.radio("Modo calendário", ["Diário","Semanal","Mensal","Anual YTD","Personalizado"])
    else:
        year=None; mode="Personalizado"

with tabs[2]:
    st.markdown("<div class='panel'><b>Upload</b><br>Use Somar ao calendário para manter mais de um ano.</div>", unsafe_allow_html=True)
    import_mode=st.radio("Modo de importação", ["Somar ao calendário","Substituir período do arquivo","Reprocessar ano inteiro do arquivo"], horizontal=True)
    uploaded=st.file_uploader("Base (.csv, .xlsx ou .xls)", type=["csv","xlsx","xls"])
    if uploaded:
        try:
            raw, original, final=read_file(uploaded); full,qg09,falhas=prepare(raw)
            st.success(f"Arquivo lido: {uploaded.name} | Linhas: {len(full)} | QG09: {len(qg09)} | Falhas QG09: {len(falhas)}")
            with st.expander("Diagnóstico de cabeçalhos"):
                st.write("Originais", original); st.write("Normalizados", final)
            st.dataframe(falhas.head(200), use_container_width=True, hide_index=True)
            if st.button("Salvar no calendário", type="primary"):
                if not falhas.empty:
                    mn=falhas.DT_HR_INSPECAO.dt.date.min(); mx=falhas.DT_HR_INSPECAO.dt.date.max()
                    if import_mode=="Substituir período do arquivo": delete_period(c,mn,mx)
                    if import_mode=="Reprocessar ano inteiro do arquivo":
                        for y in sorted(falhas.DT_HR_INSPECAO.dt.year.unique()): delete_year(c,int(y))
                    save_upload(c, uploaded.name, full, qg09, falhas, import_mode); st.rerun()
        except Exception as e: st.error(str(e))

df_all=load_calendar(c)
if df_all.empty or year is None:
    with tabs[0]: st.info("Faça upload da base.")
    with tabs[1]: st.info("Faça upload da base.")
else:
    ydf, start, end, label = period_filter(df_all, year, mode)
    st.sidebar.divider(); modelos=sorted(df_all.MODELO_CORRIGIDO.dropna().unique()); origens=sorted(df_all.POSTO_ORIGEM_FALHA.dropna().unique()); areas=sorted(df_all.C_AREA_ORIGEM_FALHA.dropna().unique())
    ms=st.sidebar.multiselect("Modelo", modelos); osel=st.sidebar.multiselect("Origem", origens); asel=st.sidebar.multiselect("Área", areas)
    filt=ydf[(ydf.DT_HR_INSPECAO>=datetime.combine(start,time(0,0)))&(ydf.DT_HR_INSPECAO<=datetime.combine(end,time(23,59,59)))].copy()
    if ms: filt=filt[filt.MODELO_CORRIGIDO.isin(ms)]
    if osel: filt=filt[filt.POSTO_ORIGEM_FALHA.isin(osel)]
    if asel: filt=filt[filt.C_AREA_ORIGEM_FALHA.isin(asel)]
    pgeral=make_pareto(filt,"D1_GERAL",top_n)
    with tabs[0]:
        st.markdown(f"<div class='small-note'>Posto: <b>QG09</b> | Recorte: <b>{label}</b> | Pareto por <b>D1_GERAL</b></div>", unsafe_allow_html=True)
        c1,c2,c3,c4=st.columns(4); c1.markdown(kpi("Falhas",fmt_int(len(filt))),unsafe_allow_html=True); c2.markdown(kpi("Top 1", pgeral.iloc[0].Item if not pgeral.empty else "-"),unsafe_allow_html=True); c3.markdown(kpi("Qtd Top 1",fmt_int(pgeral.iloc[0].Quantidade if not pgeral.empty else 0)),unsafe_allow_html=True); c4.markdown(kpi("Modelos",fmt_int(filt.MODELO_CORRIGIDO.nunique())),unsafe_allow_html=True)
        st.markdown(simple_svg(pgeral, f"Pareto Falha Geral - {label}"), unsafe_allow_html=True)
        show=pgeral.copy(); show.insert(0,"TOP",range(1,len(show)+1)); show["Percentual"]=show["Percentual"].map(fmt_pct); show["Percentual Acumulado"]=show["Percentual Acumulado"].map(fmt_pct); st.dataframe(show,use_container_width=True,hide_index=True)
    with tabs[1]:
        if pgeral.empty: st.info("Sem dados.")
        else:
            opts=[f"TOP {i+1} - {r.Item} ({r.Quantidade})" for i,r in pgeral.reset_index(drop=True).iterrows()]
            lab=st.selectbox("Escolha o TOP para estratificar", opts); idx=opts.index(lab); top=pgeral.iloc[idx].Item; df_top=filt[filt.D1_GERAL.eq(top)].copy()
            st.subheader(f"{lab}")
            by_model=make_pareto(df_top,"MODELO_CORRIGIDO",25); st.markdown("### Distribuição por modelo"); st.bar_chart(by_model.set_index("Item")["Quantidade"] if not by_model.empty else pd.Series(dtype=int)); st.dataframe(by_model.rename(columns={"Item":"Modelo"}),use_container_width=True,hide_index=True)
            modelo=st.selectbox("Escolha o modelo para ver as informações completas", ["Todos"]+sorted(df_top.MODELO_CORRIGIDO.dropna().unique()))
            df_model=df_top.copy() if modelo=="Todos" else df_top[df_top.MODELO_CORRIGIDO.eq(modelo)].copy()
            st.markdown(f"### Ranking das falhas completas - {'Todos os modelos' if modelo=='Todos' else modelo}")
            det=make_pareto(df_model,"ANOMALIA_FALHA",50).rename(columns={"Item":"Falha completa"})
            if not det.empty:
                det.insert(0,"Ranking",range(1,len(det)+1)); det["Qtd"]=det["Quantidade"]; det["Descrição ranking"]=det.apply(lambda r: f"{int(r.Ranking)} - {r['Falha completa']} (qtd-{int(r.Qtd)})",axis=1); det["Percentual"]=det["Percentual"].map(fmt_pct); det["Percentual Acumulado"]=det["Percentual Acumulado"].map(fmt_pct)
            st.dataframe(det[["Ranking","Falha completa","Qtd","Percentual","Percentual Acumulado","Descrição ranking"]] if not det.empty else det,use_container_width=True,hide_index=True)
            if modelo=="Todos" and not det.empty:
                falha_sel=st.selectbox("Escolha uma falha completa para ver os modelos envolvidos", det["Falha completa"].tolist())
                pm=make_pareto(df_model[df_model.ANOMALIA_FALHA.eq(falha_sel)],"MODELO_CORRIGIDO",25); st.bar_chart(pm.set_index("Item")["Quantidade"] if not pm.empty else pd.Series(dtype=int)); st.dataframe(pm.rename(columns={"Item":"Modelo"}),use_container_width=True,hide_index=True)
            cols=["DT_HR_INSPECAO","NR_WO","NR_SERIE","CD_MODELO","MODELO_CORRIGIDO","D1_GERAL","D1","ANOMALIA_FALHA","POSTO_ORIGEM_FALHA","C_AREA_ORIGEM_FALHA"]
            st.markdown("### Registros completos"); st.dataframe(df_model[[c for c in cols if c in df_model.columns]].sort_values(["ANOMALIA_FALHA","MODELO_CORRIGIDO","DT_HR_INSPECAO"]),use_container_width=True,hide_index=True)
with tabs[3]:
    h=history(c); st.dataframe(h,use_container_width=True,hide_index=True)
    if st.button("Limpar calendário inteiro"): clear(c); st.rerun()
