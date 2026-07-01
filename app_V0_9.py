
import io
import re
import html
import sqlite3
import unicodedata
from datetime import datetime, date, time, timedelta
from calendar import monthrange

import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Pareto Falhas QG09 - V0.9",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

APP_VERSION = "V0.9"
DB = "pareto_qg09_v09.db"
POSTO_FIXO = "QG09"

REQ = ["CD_POSTO_CN", "CD_MODELO", "DT_HR_INSPECAO", "ANOMALIA_FALHA"]
OPTIONAL = [
    "NR_WO", "NR_SERIE", "CD_PRODUTO", "C_MODELO_FAMILIA", "POSTO_ORIGEM_FALHA",
    "POSTO_ENCERRAMNTO_FALHA", "C_AREA_ORIGEM_FALHA", "CD_USER_INSPECAO",
    "C_DPU_QG_AMARELO", "D1",
]

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
.hero h1{margin:0;color:white;font-size:2.05rem}.hero p{margin:8px 0 0 0;color:#a9b8d4}.badge{display:inline-block;padding:5px 10px;border-radius:999px;border:1px solid rgba(255,255,255,.14);background:rgba(47,128,237,.14);color:#dce9ff;font-weight:700;font-size:.80rem;margin-right:6px;margin-top:10px;}
.kpi{background:linear-gradient(180deg,rgba(28,45,77,.95),rgba(18,29,52,.95));border:1px solid rgba(255,255,255,.10);border-radius:18px;padding:18px;min-height:122px;box-shadow:0 12px 30px rgba(0,0,0,.22)}
.kpi-label{color:#a9b8d4;font-size:.84rem;text-transform:uppercase;letter-spacing:.7px;font-weight:800}.kpi-value{color:#fff;font-size:1.85rem;margin-top:10px;font-weight:900;line-height:1.1}.kpi-sub{color:#a9b8d4;font-size:.85rem;margin-top:8px}
.panel{background:rgba(17,28,51,.88);border:1px solid rgba(255,255,255,.09);border-radius:20px;padding:18px;box-shadow:0 14px 32px rgba(0,0,0,.20);margin-bottom:16px}.panel-title{font-size:1.15rem;color:#fff;font-weight:900;margin-bottom:2px}.panel-sub{font-size:.92rem;color:#a9b8d4;margin-bottom:14px}.pareto-box{background:#08101f;border:1px solid rgba(255,255,255,.10);border-radius:18px;padding:14px;overflow-x:auto}svg text{font-family:Arial,sans-serif}.small-note{color:#a9b8d4;font-size:.88rem;}
</style>
"""

ALIASES = {
    "CD_POSTO_CN": ["CD_POSTO_CN", "CD_POSTO_FALHA", "CD\\_POSTO\\_FALHA", "POSTO", "POSTO_CN", "CD_POSTO", "CDPOSTOCN"],
    "CD_MODELO": ["CD_MODELO", "CD\\_MODELO", "MODELO", "COD_MODELO", "CODIGO_MODELO", "CDMODELO"],
    "DT_HR_INSPECAO": ["DT_HR_INSPECAO", "DT_CRIACAO_FALHA", "DT\\_CRIACAO\\_FALHA", "DT_ENC_CERTIFICADO", "DT_ENCERRAMENTO_FALHA", "DATA_INSPECAO", "DT_INSPECAO", "DATA_HORA_INSPECAO", "DATA"],
    "ANOMALIA_FALHA": ["ANOMALIA_FALHA", "ANOMALIA\\_FALHA", "FALHA", "ANOMALIA", "DESCRICAO_FALHA", "DESC_FALHA"],
    "NR_WO": ["NR_WO", "WO", "ORDEM", "NR_ORDEM"],
    "NR_SERIE": ["NR_SERIE", "SERIE", "CHASSI", "NR_CHASSI"],
    "POSTO_ORIGEM_FALHA": ["POSTO_ORIGEM_FALHA", "ORIGEM_FALHA", "POSTO_ORIGEM", "ORIGEM"],
    "C_AREA_ORIGEM_FALHA": ["C_AREA_ORIGEM_FALHA", "AREA_ORIGEM_FALHA", "AREA_ORIGEM"],
    "C_DPU_QG_AMARELO": ["C_DPU_QG_AMARELO", "DPU", "DPU_QG_AMARELO"],
}

# -----------------------------
# Normalização e leitura
# -----------------------------
def strip_accents(txt):
    return "".join(ch for ch in unicodedata.normalize("NFKD", str(txt)) if not unicodedata.combining(ch))

def clean_col_name(col):
    txt = str(col).replace("\ufeff", "").strip()
    txt = txt.replace("\\_", "_").replace("\\", "")
    txt = strip_accents(txt).upper().strip()
    txt = re.sub(r"[^A-Z0-9]+", "_", txt)
    return re.sub(r"_+", "_", txt).strip("_")

def normalize_columns(df):
    df = df.copy()
    original_cols = list(df.columns)
    df.columns = [clean_col_name(c) for c in df.columns]
    existing = set(df.columns)
    rename = {}
    for canonical, aliases in ALIASES.items():
        if canonical in existing:
            continue
        for alias in aliases:
            ca = clean_col_name(alias)
            if ca in existing:
                rename[ca] = canonical
                break
    if rename:
        df = df.rename(columns=rename)
    df = df.loc[:, ~df.columns.duplicated()].copy()
    return df, original_cols, list(df.columns)

def norm_text(v):
    if pd.isna(v):
        return ""
    return re.sub(r"\s+", " ", str(v).strip())

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

def falha_geral(d1, anomalia):
    """Transforma a falha completa em categoria geral para o Pareto principal.
    Ex.: 'SOLDA - CORDÃO INCOMPLETO' -> 'CORDÃO INCOMPLETO'.
    Ex.: 'PEÇA ACABAMENTO FORA DO ESPECIFICADO' -> igual.
    """
    val = norm_text(d1).upper()
    if not val:
        val = norm_text(anomalia).upper()
    # Remove prefixos operacionais que deixam o Pareto muito quebrado.
    val = re.sub(r"^(SOLDA|PE[CÇ]A|COMPONENTE)\s*[-–—]\s*", "", val).strip()
    val = re.sub(r"^SOLDA\s+", "", val).strip()
    return val if val else "NÃO INFORMADO"

def read_file(uploaded):
    ext = uploaded.name.lower().split(".")[-1]
    content = uploaded.getvalue()
    if ext == "csv":
        last_err = None
        for enc in ["utf-16", "utf-8-sig", "latin1"]:
            for sep in ["\t", ";", ",", None]:
                try:
                    raw = pd.read_csv(io.BytesIO(content), encoding=enc, sep=sep, engine="python", dtype=str)
                    return normalize_columns(raw)
                except Exception as err:
                    last_err = err
        raise ValueError(f"Não foi possível ler o CSV. Detalhe: {last_err}")
    if ext in ["xlsx", "xls"]:
        engine = "openpyxl" if ext == "xlsx" else "xlrd"
        raw = pd.read_excel(io.BytesIO(content), engine=engine, dtype=str)
        return normalize_columns(raw)
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
    df["D1"] = df["D1"].map(norm_text)
    df["D1_GERAL"] = df.apply(lambda r: falha_geral(r.get("D1", ""), r.get("ANOMALIA_FALHA", "")), axis=1)
    df["POSTO_ORIGEM_FALHA"] = df["POSTO_ORIGEM_FALHA"].map(norm_text)
    df["C_AREA_ORIGEM_FALHA"] = df["C_AREA_ORIGEM_FALHA"].map(norm_text)
    df["NR_WO"] = df["NR_WO"].map(norm_text)
    df["NR_SERIE"] = df["NR_SERIE"].map(norm_text)
    qg09 = df[df["CD_POSTO_CN"].eq(POSTO_FIXO)].copy()
    qg09 = qg09[qg09["DT_HR_INSPECAO"].notna()].copy()
    falhas = qg09[qg09["ANOMALIA_FALHA"].ne("")].copy()
    cols = ["CD_POSTO_CN", "NR_WO", "NR_SERIE", "CD_MODELO", "MODELO_CORRIGIDO", "DT_HR_INSPECAO", "ANOMALIA_FALHA", "D1", "D1_GERAL", "POSTO_ORIGEM_FALHA", "C_AREA_ORIGEM_FALHA", "C_DPU_QG_AMARELO"]
    return df, qg09[cols], falhas[cols]

# -----------------------------
# Banco local/calendário
# -----------------------------
def get_conn():
    return sqlite3.connect(DB, check_same_thread=False)

def init_db(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS upload_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_name TEXT,
            uploaded_at TEXT,
            total_rows INTEGER,
            qg09_rows INTEGER,
            falhas_rows INTEGER,
            min_date TEXT,
            max_date TEXT,
            mode TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS falhas_qg09 (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            upload_id INTEGER,
            nr_wo TEXT,
            nr_serie TEXT,
            cd_modelo TEXT,
            modelo_corrigido TEXT,
            dt_hr_inspecao TEXT,
            anomalia_falha TEXT,
            d1 TEXT,
            d1_geral TEXT,
            posto_origem_falha TEXT,
            c_area_origem_falha TEXT
        )
    """)
    conn.commit()

def ensure_v09_columns(conn):
    cols = pd.read_sql_query("PRAGMA table_info(falhas_qg09)", conn)["name"].tolist()
    if "d1" not in cols:
        conn.execute("ALTER TABLE falhas_qg09 ADD COLUMN d1 TEXT")
    if "d1_geral" not in cols:
        conn.execute("ALTER TABLE falhas_qg09 ADD COLUMN d1_geral TEXT")
    conn.commit()

def delete_period(conn, start_date, end_date):
    s = datetime.combine(start_date, time(0,0,0)).isoformat(sep=" ")
    e = datetime.combine(end_date, time(23,59,59)).isoformat(sep=" ")
    conn.execute("DELETE FROM falhas_qg09 WHERE datetime(dt_hr_inspecao) BETWEEN datetime(?) AND datetime(?)", (s, e))
    conn.commit()

def delete_year(conn, year):
    conn.execute("DELETE FROM falhas_qg09 WHERE strftime('%Y', dt_hr_inspecao)=?", (str(year),))
    conn.commit()

def save_upload(conn, file_name, full, qg09, falhas, mode):
    min_d = falhas["DT_HR_INSPECAO"].dt.date.min().isoformat() if not falhas.empty else None
    max_d = falhas["DT_HR_INSPECAO"].dt.date.max().isoformat() if not falhas.empty else None
    cur = conn.execute("""
        INSERT INTO upload_log (file_name, uploaded_at, total_rows, qg09_rows, falhas_rows, min_date, max_date, mode)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (file_name, datetime.now().isoformat(timespec="seconds"), len(full), len(qg09), len(falhas), min_d, max_d, mode))
    uid = int(cur.lastrowid)
    rows = []
    for _, r in falhas.iterrows():
        rows.append((
            uid,
            str(r.get("NR_WO", "")),
            str(r.get("NR_SERIE", "")),
            str(r.get("CD_MODELO", "")),
            str(r.get("MODELO_CORRIGIDO", "")),
            r.get("DT_HR_INSPECAO").isoformat(sep=" ", timespec="seconds") if pd.notna(r.get("DT_HR_INSPECAO")) else None,
            str(r.get("ANOMALIA_FALHA", "")),
            str(r.get("D1", "")),
            str(r.get("D1_GERAL", "")),
            str(r.get("POSTO_ORIGEM_FALHA", "")),
            str(r.get("C_AREA_ORIGEM_FALHA", "")),
        ))
    conn.executemany("""
        INSERT INTO falhas_qg09 (upload_id, nr_wo, nr_serie, cd_modelo, modelo_corrigido, dt_hr_inspecao, anomalia_falha, d1, d1_geral, posto_origem_falha, c_area_origem_falha)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, rows)
    conn.commit()
    return uid

def load_calendar(conn):
    df = pd.read_sql_query("""
        SELECT nr_wo AS NR_WO, nr_serie AS NR_SERIE, cd_modelo AS CD_MODELO, modelo_corrigido AS MODELO_CORRIGIDO,
               dt_hr_inspecao AS DT_HR_INSPECAO, anomalia_falha AS ANOMALIA_FALHA,
               d1 AS D1, d1_geral AS D1_GERAL,
               posto_origem_falha AS POSTO_ORIGEM_FALHA, c_area_origem_falha AS C_AREA_ORIGEM_FALHA
        FROM falhas_qg09
    """, conn)
    if df.empty:
        return df
    df["DT_HR_INSPECAO"] = pd.to_datetime(df["DT_HR_INSPECAO"], errors="coerce")
    df["D1"] = df["D1"].fillna("").astype(str)
    df["D1_GERAL"] = df.apply(lambda r: falha_geral(r.get("D1", ""), r.get("ANOMALIA_FALHA", "")) if not str(r.get("D1_GERAL", "")).strip() else str(r.get("D1_GERAL", "")).strip(), axis=1)
    return df.drop_duplicates(subset=["NR_WO", "NR_SERIE", "CD_MODELO", "DT_HR_INSPECAO", "ANOMALIA_FALHA", "POSTO_ORIGEM_FALHA"], keep="last").reset_index(drop=True)

def upload_history(conn):
    return pd.read_sql_query("SELECT * FROM upload_log ORDER BY id DESC", conn)

def clear_calendar(conn):
    conn.execute("DELETE FROM falhas_qg09")
    conn.execute("DELETE FROM upload_log")
    conn.commit()

# -----------------------------
# Períodos/calendário
# -----------------------------
def available_years(df):
    if df.empty:
        return []
    return sorted(df["DT_HR_INSPECAO"].dt.year.dropna().astype(int).unique().tolist())

def year_df(df, year):
    return df[df["DT_HR_INSPECAO"].dt.year.eq(int(year))].copy()

def week_options(df_year):
    if df_year.empty:
        return []
    dates = sorted(df_year["DT_HR_INSPECAO"].dt.date.unique().tolist())
    mondays = sorted({d - timedelta(days=d.weekday()) for d in dates})
    return [(f"Semana {i:02d} - {m.strftime('%d/%m/%Y')} a {(m+timedelta(days=6)).strftime('%d/%m/%Y')}", m, m+timedelta(days=6)) for i, m in enumerate(mondays, 1)]

def month_options(df_year, year):
    if df_year.empty:
        return []
    months = sorted(df_year["DT_HR_INSPECAO"].dt.month.dropna().astype(int).unique().tolist())
    return [(f"{m:02d}/{year}", date(year, m, 1), date(year, m, monthrange(year, m)[1])) for m in months]

def resolve_period(df_year, year, mode):
    min_d = df_year["DT_HR_INSPECAO"].dt.date.min()
    max_d = df_year["DT_HR_INSPECAO"].dt.date.max()
    if mode == "Diário":
        d = st.sidebar.date_input("Dia", value=max_d, min_value=min_d, max_value=max_d, format="DD/MM/YYYY")
        return d, d, d.strftime("%d/%m/%Y")
    if mode == "Semanal":
        options = week_options(df_year)
        labels = [x[0] for x in options]
        label = st.sidebar.selectbox("Semana", labels, index=len(labels)-1)
        found = next(x for x in options if x[0] == label)
        return found[1], found[2], label
    if mode == "Mensal":
        options = month_options(df_year, year)
        labels = [x[0] for x in options]
        label = st.sidebar.selectbox("Mês", labels, index=len(labels)-1)
        found = next(x for x in options if x[0] == label)
        return found[1], found[2], label
    if mode == "Anual YTD":
        return date(year, 1, 1), max_d, f"YTD {year} até {max_d.strftime('%d/%m/%Y')}"
    p = st.sidebar.date_input("Período personalizado", value=(min_d, max_d), min_value=min_d, max_value=max_d, format="DD/MM/YYYY")
    if isinstance(p, tuple) and len(p) == 2:
        return p[0], p[1], f"Personalizado: {p[0].strftime('%d/%m/%Y')} a {p[1].strftime('%d/%m/%Y')}"
    return min_d, max_d, "Personalizado"

# -----------------------------
# Pareto e SVG
# -----------------------------
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
    try: return f"{int(v):,}".replace(",", ".")
    except Exception: return "0"

def fmt_pct(v):
    try: return f"{float(v)*100:.1f}%".replace(".", ",")
    except Exception: return "0,0%"

def kpi(label, value, sub=""):
    return f"""
    <div class='kpi'><div class='kpi-label'>{html.escape(str(label))}</div><div class='kpi-value'>{html.escape(str(value))}</div><div class='kpi-sub'>{html.escape(str(sub))}</div></div>
    """

def pareto_svg(pareto, title="Pareto", width=1180, height=560):
    if pareto.empty:
        return "<div class='pareto-box'>Sem dados para exibir.</div>"
    ml, mr, mt, mb = 70, 75, 55, 150
    pw, ph = width - ml - mr, height - mt - mb
    max_q = max(float(pareto["Quantidade"].max()), 1.0)
    step = pw / max(len(pareto), 1)
    bar_w = min(step * 0.72, 72)
    def xc(i): return ml + step * i + step / 2
    def yq(q): return mt + ph - (float(q) / max_q) * ph
    def yp(p): return mt + ph - float(p) * ph
    parts = [f"<div class='pareto-box'><svg viewBox='0 0 {width} {height}' width='100%' height='{height}'>"]
    parts.append("<rect x='0' y='0' width='100%' height='100%' fill='#08101f'/>")
    parts.append(f"<text x='{ml}' y='32' fill='#ffffff' font-size='22' font-weight='800'>{html.escape(title)}</text>")
    for k in range(6):
        q = max_q * k / 5
        y = yq(q)
        parts.append(f"<line x1='{ml}' y1='{y:.1f}' x2='{width-mr}' y2='{y:.1f}' stroke='rgba(255,255,255,.10)'/>")
        parts.append(f"<text x='{ml-12}' y='{y+4:.1f}' fill='#a9b8d4' font-size='12' text-anchor='end'>{int(round(q))}</text>")
        p = k / 5
        parts.append(f"<text x='{width-mr+10}' y='{yp(p)+4:.1f}' fill='#a9b8d4' font-size='12'>{int(p*100)}%</text>")
    y80 = yp(0.8)
    parts.append(f"<line x1='{ml}' y1='{y80:.1f}' x2='{width-mr}' y2='{y80:.1f}' stroke='#f59e0b' stroke-width='2' stroke-dasharray='7 7'/>")
    parts.append(f"<text x='{width-mr-5}' y='{y80-8:.1f}' fill='#f59e0b' font-size='13' text-anchor='end'>80%</text>")
    points = []
    for i, row in pareto.reset_index(drop=True).iterrows():
        x = xc(i)
        q = float(row["Quantidade"])
        y = yq(q)
        h = mt + ph - y
        label = str(row["Item"])
        short = label[:24] + ("..." if len(label) > 24 else "")
        parts.append(f"<rect x='{x-bar_w/2:.1f}' y='{y:.1f}' width='{bar_w:.1f}' height='{h:.1f}' fill='#2f80ed' rx='4'><title>{html.escape(label)} - {int(q)}</title></rect>")
        parts.append(f"<text x='{x:.1f}' y='{max(y-7,45):.1f}' fill='#e8eefc' font-size='12' text-anchor='middle'>{int(q)}</text>")
        parts.append(f"<text x='{x:.1f}' y='{mt+ph+23}' fill='#c8d5ef' font-size='11' text-anchor='end' transform='rotate(-35 {x:.1f} {mt+ph+23})'>{html.escape(short)}</text>")
        points.append((x, yp(row["Percentual Acumulado"]), row["Percentual Acumulado"]))
    path = " ".join([f"{x:.1f},{y:.1f}" for x, y, _ in points])
    parts.append(f"<polyline points='{path}' fill='none' stroke='#ff3b30' stroke-width='3'/>")
    for x, y, p in points:
        parts.append(f"<circle cx='{x:.1f}' cy='{y:.1f}' r='5' fill='#ff3b30'><title>{p:.1%}</title></circle>")
    parts.append(f"<rect x='{ml}' y='{height-28}' width='15' height='12' fill='#2f80ed'/><text x='{ml+22}' y='{height-18}' fill='#e8eefc' font-size='12'>Quantidade</text>")
    parts.append(f"<line x1='{ml+125}' y1='{height-22}' x2='{ml+160}' y2='{height-22}' stroke='#ff3b30' stroke-width='3'/><text x='{ml+168}' y='{height-18}' fill='#e8eefc' font-size='12'>% acumulado</text>")
    parts.append("</svg></div>")
    return "".join(parts)

def apply_filters(df, modelos, origens, areas, start_date, end_date):
    out = df.copy()
    if modelos: out = out[out["MODELO_CORRIGIDO"].isin(modelos)]
    if origens: out = out[out["POSTO_ORIGEM_FALHA"].isin(origens)]
    if areas: out = out[out["C_AREA_ORIGEM_FALHA"].isin(areas)]
    out = out[(out["DT_HR_INSPECAO"] >= datetime.combine(start_date, time(0,0,0))) & (out["DT_HR_INSPECAO"] <= datetime.combine(end_date, time(23,59,59)))]
    return out

# -----------------------------
# Interface
# -----------------------------
conn = get_conn()
init_db(conn)
ensure_v09_columns(conn)
st.markdown(CSS, unsafe_allow_html=True)
st.markdown(f"""
<div class='hero'>
  <h1>Pareto de Falhas QG09</h1>
  <p>Versão {APP_VERSION}: Pareto por falha geral, estratificação por modelo e detalhamento da falha completa.</p>
  <span class='badge'>Pareto por D1 geral</span><span class='badge'>TOP por modelo</span><span class='badge'>Detalhe completo</span><span class='badge'>Apenas QG09</span>
</div>
""", unsafe_allow_html=True)

df_all = load_calendar(conn)

tabs = st.tabs(["Dashboard", "Estratificar TOP", "Pareto por Modelo", "Origem da Falha", "Base & Upload", "Histórico", "Sobre"])

with st.sidebar:
    st.subheader("Configurações")
    top_n = st.slider("Top N", 5, 25, 10, 1)
    st.caption("O calendário considera somente registros cujo posto de falha é QG09.")
    years = available_years(df_all)
    if years:
        year = st.selectbox("Ano", years, index=len(years)-1)
        mode = st.radio("Modo calendário", ["Diário", "Semanal", "Mensal", "Anual YTD", "Personalizado"])
    else:
        year = None
        mode = "Personalizado"

with tabs[4]:
    st.markdown("<div class='panel'><div class='panel-title'>Base & Upload</div><div class='panel-sub'>Use Somar ao calendário para carregar 2025 e depois 2026 sem apagar o anterior.</div>", unsafe_allow_html=True)
    import_mode = st.radio("Modo de importação", ["Somar ao calendário", "Substituir período do arquivo", "Reprocessar ano inteiro do arquivo"], horizontal=True)
    uploaded = st.file_uploader("Base operacional (.xlsx, .xls ou .csv)", type=["xlsx", "xls", "csv"])
    if uploaded:
        try:
            raw, original_cols, final_cols = read_file(uploaded)
            ok, missing = validate(raw)
            with st.expander("Diagnóstico dos cabeçalhos lidos"):
                st.write("Cabeçalhos originais:")
                st.write(original_cols)
                st.write("Cabeçalhos normalizados pelo site:")
                st.write(final_cols)
            if not ok:
                st.error("Colunas obrigatórias ausentes após normalização: " + ", ".join(missing))
            else:
                full, qg09, falhas = prepare(raw)
                st.success(f"Arquivo lido: {uploaded.name} | Linhas: {len(full)} | QG09: {len(qg09)} | Falhas QG09: {len(falhas)}")
                c1, c2, c3 = st.columns(3)
                c1.metric("Linhas originais", fmt_int(len(full)))
                c2.metric("Linhas QG09", fmt_int(len(qg09)))
                c3.metric("Falhas QG09", fmt_int(len(falhas)))
                st.dataframe(falhas.head(200), use_container_width=True, hide_index=True)
                if st.button("Salvar no calendário", type="primary", use_container_width=True):
                    if falhas.empty:
                        st.error("Não há falhas QG09 para salvar.")
                    else:
                        min_d = falhas["DT_HR_INSPECAO"].dt.date.min()
                        max_d = falhas["DT_HR_INSPECAO"].dt.date.max()
                        if import_mode == "Substituir período do arquivo":
                            delete_period(conn, min_d, max_d)
                        elif import_mode == "Reprocessar ano inteiro do arquivo":
                            for y in sorted(falhas["DT_HR_INSPECAO"].dt.year.dropna().astype(int).unique().tolist()):
                                delete_year(conn, y)
                        uid = save_upload(conn, uploaded.name, full, qg09, falhas, import_mode)
                        st.success(f"Upload {uid} salvo no calendário. Modo: {import_mode}.")
                        st.rerun()
        except Exception as e:
            st.error(f"Erro ao processar arquivo: {e}")
    st.markdown("</div>", unsafe_allow_html=True)

# Recarrega após upload
_df_all = load_calendar(conn)
if not _df_all.empty:
    df_all = _df_all

if df_all.empty or year is None:
    for idx in [0, 1, 2, 3]:
        with tabs[idx]: st.info("Faça upload da base na aba Base & Upload.")
else:
    df_year = year_df(df_all, year)
    start_date, end_date, period_label = resolve_period(df_year, year, mode)
    with st.sidebar:
        modelos = sorted([x for x in df_all["MODELO_CORRIGIDO"].dropna().unique().tolist() if x])
        origens = sorted([x for x in df_all["POSTO_ORIGEM_FALHA"].dropna().unique().tolist() if x])
        areas = sorted([x for x in df_all["C_AREA_ORIGEM_FALHA"].dropna().unique().tolist() if x])
        modelos_sel = st.multiselect("Modelo corrigido", modelos)
        origens_sel = st.multiselect("Origem da falha", origens, help="Origem da falha dos registros QG09. O posto considerado continua sendo somente QG09.")
        areas_sel = st.multiselect("Área origem da falha", areas)
    filt = apply_filters(df_year, modelos_sel, origens_sel, areas_sel, start_date, end_date)
    pareto_geral = make_pareto(filt, "D1_GERAL", top_n)

    with tabs[0]:
        total = len(filt)
        top_item = pareto_geral.iloc[0]["Item"] if not pareto_geral.empty else "Sem dados"
        top_qtd = pareto_geral.iloc[0]["Quantidade"] if not pareto_geral.empty else 0
        modelo_top = filt["MODELO_CORRIGIDO"].value_counts().idxmax() if not filt.empty else "Sem dados"
        acum = pareto_geral["Percentual Acumulado"].iloc[-1] if not pareto_geral.empty else 0
        st.markdown(f"<div class='small-note'>Posto considerado: <b>QG09</b> | Ano: <b>{year}</b> | Recorte: <b>{period_label}</b> | Pareto principal por <b>D1_GERAL</b></div>", unsafe_allow_html=True)
        k1, k2, k3, k4 = st.columns(4)
        k1.markdown(kpi("Falhas QG09", fmt_int(total), "Após filtros"), unsafe_allow_html=True)
        k2.markdown(kpi("Modelo mais afetado", modelo_top, "Maior volume"), unsafe_allow_html=True)
        k3.markdown(kpi("Falha geral Top 1", fmt_int(top_qtd), str(top_item)[:90]), unsafe_allow_html=True)
        k4.markdown(kpi("Acumulado Top", fmt_pct(acum), f"Top {top_n}"), unsafe_allow_html=True)
        st.markdown("<div class='panel'><div class='panel-title'>Pareto clássico por falha geral</div><div class='panel-sub'>Agora o Pareto agrupa por D1_GERAL, por exemplo: PEÇA ACABAMENTO FORA DO ESPECIFICADO, CORDÃO INCOMPLETO, RESPINGOS etc.</div>", unsafe_allow_html=True)
        st.markdown(pareto_svg(pareto_geral, f"Pareto de Falhas Gerais QG09 - {period_label} - Top {top_n}"), unsafe_allow_html=True)
        show = pareto_geral.copy()
        if not show.empty:
            show.insert(0, "TOP", range(1, len(show)+1))
            show["Percentual"] = show["Percentual"].map(fmt_pct)
            show["Percentual Acumulado"] = show["Percentual Acumulado"].map(fmt_pct)
        st.dataframe(show, use_container_width=True, hide_index=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with tabs[1]:
        st.markdown("<div class='panel'><div class='panel-title'>Estratificar TOP escolhido</div><div class='panel-sub'>Escolha uma falha geral do Pareto, veja quais modelos aparecem e depois veja a falha completa dentro do modelo escolhido.</div>", unsafe_allow_html=True)
        if pareto_geral.empty:
            st.info("Sem dados para estratificar.")
        else:
            opts = [f"TOP {i+1} - {row.Item} ({row.Quantidade})" for i, row in pareto_geral.reset_index(drop=True).iterrows()]
            sel_label = st.selectbox("Escolha o TOP para estratificar", opts)
            sel_idx = opts.index(sel_label)
            sel_top = pareto_geral.iloc[sel_idx]["Item"]
            df_top = filt[filt["D1_GERAL"].eq(sel_top)].copy()
            c1, c2, c3 = st.columns(3)
            c1.metric("TOP escolhido", f"TOP {sel_idx+1}")
            c2.metric("Falha geral", sel_top)
            c3.metric("Ocorrências", fmt_int(len(df_top)))

            by_model = make_pareto(df_top, "MODELO_CORRIGIDO", 25)
            st.markdown("### Distribuição por modelo")
            if not by_model.empty:
                st.bar_chart(by_model.set_index("Item")["Quantidade"])
            st.dataframe(by_model.rename(columns={"Item":"Modelo"}), use_container_width=True, hide_index=True)

            modelos_top = sorted(df_top["MODELO_CORRIGIDO"].dropna().unique().tolist())
            modelo_escolhido = st.selectbox("Escolha o modelo para ver as informações completas", modelos_top)
            df_model = df_top[df_top["MODELO_CORRIGIDO"].eq(modelo_escolhido)].copy()
            st.markdown(f"### Detalhe completo - {sel_top} / {modelo_escolhido}")

            detalhe_pareto = make_pareto(df_model, "ANOMALIA_FALHA", 25)
            st.markdown("#### Falhas completas mais recorrentes dentro do TOP e modelo escolhidos")
            st.dataframe(detalhe_pareto.rename(columns={"Item":"Falha completa"}), use_container_width=True, hide_index=True)

            cols_det = ["DT_HR_INSPECAO", "NR_WO", "NR_SERIE", "CD_MODELO", "MODELO_CORRIGIDO", "D1_GERAL", "D1", "ANOMALIA_FALHA", "POSTO_ORIGEM_FALHA", "C_AREA_ORIGEM_FALHA"]
            cols_det = [c for c in cols_det if c in df_model.columns]
            st.markdown("#### Registros completos")
            st.dataframe(df_model[cols_det].sort_values(["DT_HR_INSPECAO", "ANOMALIA_FALHA"]), use_container_width=True, hide_index=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with tabs[2]:
        st.markdown("<div class='panel'><div class='panel-title'>Pareto por Modelo</div><div class='panel-sub'>Dentro do modelo selecionado, o Pareto também usa falha geral.</div>", unsafe_allow_html=True)
        modelo = st.selectbox("Modelo", modelos)
        p = make_pareto(filt[filt["MODELO_CORRIGIDO"].eq(modelo)], "D1_GERAL", top_n)
        st.markdown(pareto_svg(p, f"Pareto Falha Geral - {modelo} - {period_label} - Top {top_n}"), unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with tabs[3]:
        st.markdown("<div class='panel'><div class='panel-title'>Pareto por Origem da Falha</div><div class='panel-sub'>Mostra a origem das falhas dos registros do QG09. O filtro principal continua fixo em QG09.</div>", unsafe_allow_html=True)
        p = make_pareto(filt, "POSTO_ORIGEM_FALHA", top_n)
        st.markdown(pareto_svg(p, f"Pareto de Origem da Falha - {period_label} - Top {top_n}"), unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

with tabs[5]:
    st.markdown("<div class='panel'><div class='panel-title'>Histórico do calendário</div><div class='panel-sub'>Arquivos salvos no calendário acumulativo.</div>", unsafe_allow_html=True)
    hist = upload_history(conn)
    if hist.empty:
        st.info("Nenhum upload salvo ainda.")
    else:
        st.dataframe(hist, use_container_width=True, hide_index=True)
    if st.button("Limpar calendário inteiro", use_container_width=True):
        clear_calendar(conn)
        st.success("Calendário limpo.")
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

with tabs[6]:
    st.markdown("<div class='panel'><div class='panel-title'>Sobre</div><div class='panel-sub'>Versão V0.9 com Pareto geral e estratificação de TOP.</div>", unsafe_allow_html=True)
    st.markdown("""
### Regras da V0.9
- Considera somente falhas cujo posto é `QG09`.
- O Pareto principal não usa mais a falha completa inteira.
- O Pareto principal usa `D1_GERAL`, por exemplo:
  - `PEÇA ACABAMENTO FORA DO ESPECIFICADO`
  - `CORDÃO INCOMPLETO`
  - `RESPINGOS`
- Na aba `Estratificar TOP`, você escolhe o TOP do Pareto geral.
- Depois o app mostra quais modelos aparecem dentro daquele TOP.
- Ao escolher um modelo, o app mostra as falhas completas, por exemplo:
  `GLAZED FRAME V2 MF ESTR. TRASEIRA PONTO 124 PEÇA ACABAMENTO FORA DO ESPECIFICADO`.
""")
    st.markdown("</div>", unsafe_allow_html=True)
