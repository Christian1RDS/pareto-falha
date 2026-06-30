import io
import html
from datetime import datetime, time
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Pareto Falhas QG09 - V0.5",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

APP_VERSION = "V0.5"
POSTO_FIXO = "QG09"
REQ = ["CD_POSTO_CN", "CD_MODELO", "DT_HR_INSPECAO", "ANOMALIA_FALHA"]
OPTIONAL = ["NR_WO", "NR_SERIE", "POSTO_ORIGEM_FALHA", "CD_USER_INSPECAO", "C_DPU_QG_AMARELO"]

MAPA_MODELOS = {
    "VTBAGFC": "VTBA",
    "V2MFGFC": "V2 MF",
    "V2VTGFC": "V2 VT",
    "G7GFCAN": "G7",
    "G8GFCAN": "G8",
}

CSS = """
<style>
.stApp{background:radial-gradient(circle at top left,#1b2e54 0,#0b1324 38%,#08101f 100%);color:#e8eefc;}
[data-testid="stSidebar"]{background:linear-gradient(180deg,#0e1930 0%,#0a1222 100%);}
.block-container{padding-top:1.2rem;padding-bottom:2rem;}
.hero{padding:24px 28px;border:1px solid rgba(255,255,255,.10);background:linear-gradient(135deg,rgba(47,128,237,.22),rgba(18,29,52,.94));border-radius:22px;box-shadow:0 18px 45px rgba(0,0,0,.25);margin-bottom:18px;}
.hero h1{margin:0;color:white;font-size:2.05rem;}.hero p{margin:8px 0 0 0;color:#a9b8d4;}
.badge{display:inline-block;padding:5px 10px;border-radius:999px;border:1px solid rgba(255,255,255,.14);background:rgba(47,128,237,.14);color:#dce9ff;font-weight:700;font-size:.80rem;margin-right:6px;margin-top:10px;}
.kpi{background:linear-gradient(180deg,rgba(28,45,77,.95),rgba(18,29,52,.95));border:1px solid rgba(255,255,255,.10);border-radius:18px;padding:18px;min-height:122px;box-shadow:0 12px 30px rgba(0,0,0,.22);}
.kpi-label{color:#a9b8d4;font-size:.84rem;text-transform:uppercase;letter-spacing:.7px;font-weight:800;}.kpi-value{color:#fff;font-size:1.85rem;margin-top:10px;font-weight:900;line-height:1.1;}.kpi-sub{color:#a9b8d4;font-size:.85rem;margin-top:8px;}
.panel{background:rgba(17,28,51,.88);border:1px solid rgba(255,255,255,.09);border-radius:20px;padding:18px;box-shadow:0 14px 32px rgba(0,0,0,.20);margin-bottom:16px;}.panel-title{font-size:1.15rem;color:#fff;font-weight:900;margin-bottom:2px;}.panel-sub{font-size:.92rem;color:#a9b8d4;margin-bottom:14px;}
.pareto-box{background:#08101f;border:1px solid rgba(255,255,255,.10);border-radius:18px;padding:14px;overflow-x:auto;}svg text{font-family:Arial,sans-serif;}
</style>
"""

def norm_text(v):
    if pd.isna(v):
        return ""
    return str(v).strip()

def norm_posto(v):
    t = norm_text(v).upper()
    return "QG09" if "QG09" in t else t

def corrige_modelo(v):
    code = norm_text(v).upper()
    return MAPA_MODELOS.get(code, code if code else "Não informado")

def parse_dt(series):
    dt = pd.to_datetime(series, errors="coerce")
    mask = dt.isna() & series.notna()
    if mask.any():
        dt.loc[mask] = pd.to_datetime(series[mask], errors="coerce", dayfirst=True)
    return dt

def read_file(uploaded):
    ext = uploaded.name.lower().split(".")[-1]
    content = uploaded.getvalue()
    if ext == "csv":
        last_err = None
        for enc in ["utf-8-sig", "utf-16", "latin1"]:
            for sep in [None, "\t", ";", ","]:
                try:
                    if sep is None:
                        df = pd.read_csv(io.BytesIO(content), encoding=enc, sep=None, engine="python", dtype=str)
                    else:
                        df = pd.read_csv(io.BytesIO(content), encoding=enc, sep=sep, dtype=str)
                    df.columns = [str(c).strip().replace("\ufeff", "") for c in df.columns]
                    return df
                except Exception as err:
                    last_err = err
        raise ValueError(f"Não foi possível ler o CSV. Detalhe: {last_err}")
    if ext in ["xlsx", "xls"]:
        engine = "openpyxl" if ext == "xlsx" else "xlrd"
        df = pd.read_excel(io.BytesIO(content), engine=engine, dtype=str)
        df.columns = [str(c).strip().replace("\ufeff", "") for c in df.columns]
        return df
    raise ValueError("Formato não suportado. Use .xlsx, .xls ou .csv")

def validate(df):
    missing = [c for c in REQ if c not in df.columns]
    return len(missing) == 0, missing

def prepare(raw):
    df = raw.copy()
    for col in OPTIONAL:
        if col not in df.columns:
            df[col] = ""
    df["CD_POSTO_CN"] = df["CD_POSTO_CN"].map(norm_posto)
    df["CD_MODELO"] = df["CD_MODELO"].map(lambda x: norm_text(x).upper())
    df["MODELO_CORRIGIDO"] = df["CD_MODELO"].map(corrige_modelo)
    df["DT_HR_INSPECAO"] = parse_dt(df["DT_HR_INSPECAO"])
    df["ANOMALIA_FALHA"] = df["ANOMALIA_FALHA"].map(norm_text)
    df["POSTO_ORIGEM_FALHA"] = df["POSTO_ORIGEM_FALHA"].map(norm_text)
    df["NR_WO"] = df["NR_WO"].map(norm_text)
    df["NR_SERIE"] = df["NR_SERIE"].map(norm_text)
    df["CD_USER_INSPECAO"] = df["CD_USER_INSPECAO"].map(norm_text)
    qg09 = df[df["CD_POSTO_CN"].eq(POSTO_FIXO)].copy()
    qg09 = qg09[qg09["DT_HR_INSPECAO"].notna()].copy()
    falhas = qg09[qg09["ANOMALIA_FALHA"].ne("")].copy()
    cols = ["CD_POSTO_CN","NR_WO","NR_SERIE","CD_MODELO","MODELO_CORRIGIDO","DT_HR_INSPECAO","ANOMALIA_FALHA","POSTO_ORIGEM_FALHA","CD_USER_INSPECAO"]
    return df, qg09[cols], falhas[cols]

def make_pareto(df, col, top_n):
    if df.empty or col not in df.columns:
        return pd.DataFrame(columns=["Item", "Quantidade", "Percentual", "Percentual Acumulado"])
    s = df[col].fillna("").astype(str).str.strip()
    s = s[s.ne("")]
    if s.empty:
        return pd.DataFrame(columns=["Item", "Quantidade", "Percentual", "Percentual Acumulado"])
    out = s.value_counts().head(int(top_n)).reset_index()
    out.columns = ["Item", "Quantidade"]
    total = out["Quantidade"].sum()
    out["Percentual"] = out["Quantidade"] / total if total else 0
    out["Percentual Acumulado"] = out["Percentual"].cumsum()
    return out

def fmt_int(v):
    try:
        return f"{int(v):,}".replace(",", ".")
    except Exception:
        return "0"

def fmt_pct(v):
    try:
        return f"{float(v)*100:.1f}%".replace(".", ",")
    except Exception:
        return "0,0%"

def kpi(label, value, sub=""):
    return f"""
    <div class='kpi'>
      <div class='kpi-label'>{html.escape(str(label))}</div>
      <div class='kpi-value'>{html.escape(str(value))}</div>
      <div class='kpi-sub'>{html.escape(str(sub))}</div>
    </div>
    """

def pareto_svg(pareto, title="Pareto", width=1180, height=560):
    if pareto.empty:
        return "<div class='pareto-box'>Sem dados para exibir.</div>"
    ml, mr, mt, mb = 70, 75, 55, 145
    pw, ph = width - ml - mr, height - mt - mb
    n = len(pareto)
    max_q = max(float(pareto["Quantidade"].max()), 1.0)
    step = pw / max(n, 1)
    bar_w = min(step * 0.72, 72)
    def xc(i): return ml + step * i + step/2
    def yq(q): return mt + ph - (float(q) / max_q) * ph
    def yp(p): return mt + ph - float(p) * ph
    parts = [f"<div class='pareto-box'><svg viewBox='0 0 {width} {height}' width='100%' height='{height}'>"]
    parts.append("<rect x='0' y='0' width='100%' height='100%' fill='#08101f'/>")
    parts.append(f"<text x='{ml}' y='32' fill='#ffffff' font-size='22' font-weight='800'>{html.escape(title)}</text>")
    for k in range(6):
        q = max_q*k/5; y = yq(q)
        parts.append(f"<line x1='{ml}' y1='{y:.1f}' x2='{width-mr}' y2='{y:.1f}' stroke='rgba(255,255,255,.10)'/>")
        parts.append(f"<text x='{ml-12}' y='{y+4:.1f}' fill='#a9b8d4' font-size='12' text-anchor='end'>{int(round(q))}</text>")
        p = k/5; y2 = yp(p)
        parts.append(f"<text x='{width-mr+10}' y='{y2+4:.1f}' fill='#a9b8d4' font-size='12'>{int(p*100)}%</text>")
    y80 = yp(0.8)
    parts.append(f"<line x1='{ml}' y1='{y80:.1f}' x2='{width-mr}' y2='{y80:.1f}' stroke='#f59e0b' stroke-width='2' stroke-dasharray='7 7'/>")
    parts.append(f"<text x='{width-mr-5}' y='{y80-8:.1f}' fill='#f59e0b' font-size='13' text-anchor='end'>80%</text>")
    parts.append(f"<line x1='{ml}' y1='{mt}' x2='{ml}' y2='{mt+ph}' stroke='rgba(255,255,255,.35)'/>")
    parts.append(f"<line x1='{ml}' y1='{mt+ph}' x2='{width-mr}' y2='{mt+ph}' stroke='rgba(255,255,255,.35)'/>")
    parts.append(f"<line x1='{width-mr}' y1='{mt}' x2='{width-mr}' y2='{mt+ph}' stroke='rgba(255,255,255,.35)'/>")
    points=[]
    for i,row in pareto.reset_index(drop=True).iterrows():
        x = xc(i); q=float(row["Quantidade"]); y=yq(q); h=mt+ph-y
        label=str(row["Item"]); short=label[:22]+("..." if len(label)>22 else "")
        parts.append(f"<rect x='{x-bar_w/2:.1f}' y='{y:.1f}' width='{bar_w:.1f}' height='{h:.1f}' fill='#2f80ed' rx='4'><title>{html.escape(label)} - {int(q)}</title></rect>")
        parts.append(f"<text x='{x:.1f}' y='{max(y-7,45):.1f}' fill='#e8eefc' font-size='12' text-anchor='middle'>{int(q)}</text>")
        parts.append(f"<text x='{x:.1f}' y='{mt+ph+18}' fill='#c8d5ef' font-size='11' text-anchor='end' transform='rotate(-35 {x:.1f} {mt+ph+18})'>{html.escape(short)}</text>")
        points.append((x, yp(row["Percentual Acumulado"]), row["Percentual Acumulado"]))
    path=" ".join([f"{x:.1f},{y:.1f}" for x,y,_ in points])
    parts.append(f"<polyline points='{path}' fill='none' stroke='#ff3b30' stroke-width='3'/>")
    for x,y,p in points:
        parts.append(f"<circle cx='{x:.1f}' cy='{y:.1f}' r='5' fill='#ff3b30'><title>{p:.1%}</title></circle>")
    parts.append(f"<rect x='{ml}' y='{height-28}' width='15' height='12' fill='#2f80ed'/><text x='{ml+22}' y='{height-18}' fill='#e8eefc' font-size='12'>Quantidade</text>")
    parts.append(f"<line x1='{ml+125}' y1='{height-22}' x2='{ml+160}' y2='{height-22}' stroke='#ff3b30' stroke-width='3'/><text x='{ml+168}' y='{height-18}' fill='#e8eefc' font-size='12'>% acumulado</text>")
    parts.append("</svg></div>")
    return "".join(parts)

def apply_filters(df, modelos, origens, period):
    out = df.copy()
    if modelos:
        out = out[out["MODELO_CORRIGIDO"].isin(modelos)]
    if origens:
        out = out[out["POSTO_ORIGEM_FALHA"].isin(origens)]
    if period and len(period) == 2:
        start,end = period
        out = out[(out["DT_HR_INSPECAO"] >= datetime.combine(start,time(0,0,0))) & (out["DT_HR_INSPECAO"] <= datetime.combine(end,time(23,59,59)))]
    return out

st.markdown(CSS, unsafe_allow_html=True)
st.markdown(f"""
<div class='hero'>
  <h1>Pareto de Falhas QG09</h1>
  <p>Versão {APP_VERSION} sem Plotly: Pareto clássico em SVG interno para evitar erro de dependência.</p>
  <span class='badge'>Filtro fixo: QG09</span><span class='badge'>Sem Plotly</span><span class='badge'>Top 10 clássico</span><span class='badge'>Correção automática de modelos</span>
</div>
""", unsafe_allow_html=True)

if "base_tratada" not in st.session_state:
    st.session_state.base_tratada = pd.DataFrame()

with st.sidebar:
    st.subheader("Configurações")
    top_n = st.slider("Top N", 5, 25, 10, 1)
    st.caption("Mapeamento automático:")
    for k,v in MAPA_MODELOS.items():
        st.caption(f"{k} → {v}")

tabs = st.tabs(["Dashboard", "Pareto por Modelo", "Origem da Falha", "Base & Upload", "Sobre"])

with tabs[3]:
    st.markdown("<div class='panel'><div class='panel-title'>Base & Upload</div><div class='panel-sub'>Carregue Excel/CSV. O site filtra QG09, cria MODELO_CORRIGIDO e usa somente ANOMALIA_FALHA preenchida.</div>", unsafe_allow_html=True)
    uploaded = st.file_uploader("Base operacional (.xlsx, .xls ou .csv)", type=["xlsx","xls","csv"])
    if uploaded:
        try:
            raw = read_file(uploaded)
            ok, missing = validate(raw)
            if not ok:
                st.error("Colunas obrigatórias ausentes: " + ", ".join(missing))
            else:
                full, qg09, falhas = prepare(raw)
                st.session_state.base_tratada = falhas
                st.success(f"Arquivo lido: {uploaded.name} | Linhas: {len(full)} | QG09: {len(qg09)} | Falhas QG09: {len(falhas)}")
                c1,c2,c3 = st.columns(3)
                c1.metric("Linhas originais", fmt_int(len(full)))
                c2.metric("Linhas QG09", fmt_int(len(qg09)))
                c3.metric("Falhas QG09", fmt_int(len(falhas)))
                st.dataframe(falhas.head(200), use_container_width=True, hide_index=True)
        except Exception as e:
            st.error(f"Erro ao processar arquivo: {e}")
    st.markdown("</div>", unsafe_allow_html=True)

df = st.session_state.base_tratada

if df.empty:
    with tabs[0]: st.info("Faça upload da base na aba Base & Upload.")
    with tabs[1]: st.info("Faça upload da base na aba Base & Upload.")
    with tabs[2]: st.info("Faça upload da base na aba Base & Upload.")
else:
    with st.sidebar:
        st.divider()
        st.subheader("Filtros")
        min_d = df["DT_HR_INSPECAO"].dt.date.min(); max_d = df["DT_HR_INSPECAO"].dt.date.max()
        period = st.date_input("Período", value=(min_d,max_d), min_value=min_d, max_value=max_d, format="DD/MM/YYYY")
        modelos = sorted([x for x in df["MODELO_CORRIGIDO"].dropna().unique().tolist() if x])
        origens = sorted([x for x in df["POSTO_ORIGEM_FALHA"].dropna().unique().tolist() if x])
        modelos_sel = st.multiselect("Modelo corrigido", modelos)
        origens_sel = st.multiselect("Posto origem da falha", origens)
    filt = apply_filters(df, modelos_sel, origens_sel, period)
    pareto = make_pareto(filt, "ANOMALIA_FALHA", top_n)
    with tabs[0]:
        total = len(filt)
        top_item = pareto.iloc[0]["Item"] if not pareto.empty else "Sem dados"
        top_qtd = pareto.iloc[0]["Quantidade"] if not pareto.empty else 0
        modelo_top = filt["MODELO_CORRIGIDO"].value_counts().idxmax() if not filt.empty else "Sem dados"
        acum = pareto["Percentual Acumulado"].iloc[-1] if not pareto.empty else 0
        k1,k2,k3,k4 = st.columns(4)
        k1.markdown(kpi("Falhas QG09", fmt_int(total), "Após filtros"), unsafe_allow_html=True)
        k2.markdown(kpi("Modelo mais afetado", modelo_top, "Maior volume"), unsafe_allow_html=True)
        k3.markdown(kpi("Falha Top 1", fmt_int(top_qtd), str(top_item)[:90]), unsafe_allow_html=True)
        k4.markdown(kpi("Acumulado Top", fmt_pct(acum), f"Top {top_n}"), unsafe_allow_html=True)
        st.markdown("<div class='panel'><div class='panel-title'>Pareto clássico de falhas</div><div class='panel-sub'>Barras azuis = quantidade. Linha vermelha = percentual acumulado. Linha pontilhada = 80%.</div>", unsafe_allow_html=True)
        st.markdown(pareto_svg(pareto, f"Pareto de Falhas QG09 - Top {top_n}"), unsafe_allow_html=True)
        show = pareto.copy()
        if not show.empty:
            show["Percentual"] = show["Percentual"].map(fmt_pct)
            show["Percentual Acumulado"] = show["Percentual Acumulado"].map(fmt_pct)
        st.dataframe(show, use_container_width=True, hide_index=True)
        st.markdown("</div>", unsafe_allow_html=True)
    with tabs[1]:
        st.markdown("<div class='panel'><div class='panel-title'>Pareto por Modelo</div><div class='panel-sub'>Analise o Top de falhas dentro de um modelo corrigido.</div>", unsafe_allow_html=True)
        modelo = st.selectbox("Modelo", modelos)
        p = make_pareto(filt[filt["MODELO_CORRIGIDO"].eq(modelo)], "ANOMALIA_FALHA", top_n)
        st.markdown(pareto_svg(p, f"Pareto - {modelo} - Top {top_n}"), unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
    with tabs[2]:
        st.markdown("<div class='panel'><div class='panel-title'>Pareto por Origem da Falha</div><div class='panel-sub'>Ranking dos postos/origens mais recorrentes.</div>", unsafe_allow_html=True)
        p = make_pareto(filt, "POSTO_ORIGEM_FALHA", top_n)
        st.markdown(pareto_svg(p, f"Pareto de Origem da Falha - Top {top_n}"), unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

with tabs[4]:
    st.markdown("<div class='panel'><div class='panel-title'>Sobre</div><div class='panel-sub'>Versão V0.5 com nomes versionados e sem dependência de Plotly.</div>", unsafe_allow_html=True)
    st.markdown("""
### Regras do site
- Filtra automaticamente `CD_POSTO_CN = QG09`.
- Usa `ANOMALIA_FALHA` para montar o Pareto principal.
- Remove linhas sem falha preenchida.
- Cria a coluna `MODELO_CORRIGIDO` automaticamente.

### Mapeamento aplicado
```text
VTBAGFC  -> VTBA
V2MFGFC  -> V2 MF
V2VTGFC  -> V2 VT
G7GFCAN  -> G7
G8GFCAN  -> G8
```
""")
    st.markdown("</div>", unsafe_allow_html=True)
