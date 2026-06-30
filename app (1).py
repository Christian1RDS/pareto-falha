import io
import sqlite3
from datetime import datetime, date, time
import pandas as pd
import streamlit as st
import plotly.graph_objects as go

try:
    from streamlit_local_storage import LocalStorage
except Exception:
    LocalStorage = None

# =========================================================
# Configuracao geral
# =========================================================
st.set_page_config(
    page_title="Pareto de Falhas QG09",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

APP_VERSION = "V1.0.0"
DB = "pareto_qg09_local.db"
LS_PREFIX = "pareto_qg09_v100_"
POSTO_FIXO = "QG09"

REQ = [
    "CD_POSTO_CN",
    "CD_MODELO",
    "DT_HR_INSPECAO",
    "ANOMALIA_FALHA",
]

OPTIONAL_COLS = [
    "NR_WO",
    "NR_SERIE",
    "POSTO_ORIGEM_FALHA",
    "CD_USER_INSPECAO",
    "C_DPU_QG_AMARELO",
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
:root{
    --bg-0:#0b1324;
    --bg-1:#111c33;
    --bg-2:#172542;
    --card:#15233d;
    --card-2:#1c2d4d;
    --text:#e8eefc;
    --muted:#a9b8d4;
    --line:#2f4166;
    --blue:#2f80ed;
    --red:#ff3b30;
    --green:#21c45d;
    --amber:#f59e0b;
}
.stApp{
    background: radial-gradient(circle at top left, #1b2e54 0, #0b1324 34%, #08101f 100%);
    color: var(--text);
}
[data-testid="stSidebar"]{
    background: linear-gradient(180deg, #0e1930 0%, #0a1222 100%);
    border-right: 1px solid rgba(255,255,255,.08);
}
.block-container{
    padding-top: 1.2rem;
    padding-bottom: 2rem;
}
.main-title{
    padding: 24px 28px;
    border: 1px solid rgba(255,255,255,.10);
    background: linear-gradient(135deg, rgba(47,128,237,.22), rgba(18,29,52,.92));
    border-radius: 22px;
    box-shadow: 0 18px 45px rgba(0,0,0,.25);
    margin-bottom: 18px;
}
.main-title h1{
    margin: 0;
    font-size: 2.05rem;
    letter-spacing: .2px;
    color: #ffffff;
}
.main-title p{
    margin: 8px 0 0 0;
    color: var(--muted);
    font-size: 1rem;
}
.kpi-card{
    background: linear-gradient(180deg, rgba(28,45,77,.95), rgba(18,29,52,.95));
    border: 1px solid rgba(255,255,255,.10);
    border-radius: 18px;
    padding: 18px 18px 16px 18px;
    min-height: 124px;
    box-shadow: 0 12px 30px rgba(0,0,0,.22);
}
.kpi-label{
    color: var(--muted);
    font-size: .88rem;
    text-transform: uppercase;
    letter-spacing: .7px;
    font-weight: 700;
}
.kpi-value{
    color: #ffffff;
    font-size: 2rem;
    line-height: 1.1;
    margin-top: 10px;
    font-weight: 800;
}
.kpi-sub{
    color: var(--muted);
    font-size: .86rem;
    margin-top: 8px;
}
.section-card{
    background: rgba(17,28,51,.88);
    border: 1px solid rgba(255,255,255,.09);
    border-radius: 20px;
    padding: 20px;
    box-shadow: 0 14px 32px rgba(0,0,0,.20);
    margin-bottom: 16px;
}
.section-title{
    color: #ffffff;
    font-size: 1.20rem;
    font-weight: 800;
    margin-bottom: 4px;
}
.section-sub{
    color: var(--muted);
    font-size: .94rem;
    margin-bottom: 12px;
}
.badge{
    display:inline-block;
    padding: 5px 10px;
    border-radius: 999px;
    border:1px solid rgba(255,255,255,.14);
    background: rgba(47,128,237,.14);
    color:#dce9ff;
    font-weight:700;
    font-size:.80rem;
    margin-right:6px;
}
.stTabs [data-baseweb="tab-list"]{
    gap: 8px;
}
.stTabs [data-baseweb="tab"]{
    background: rgba(21,35,61,.75);
    border-radius: 14px 14px 0 0;
    border: 1px solid rgba(255,255,255,.08);
    color: var(--muted);
    padding: 10px 16px;
}
.stTabs [aria-selected="true"]{
    color:#ffffff !important;
    background: rgba(47,128,237,.25) !important;
}
[data-testid="stDataFrame"]{
    border-radius: 14px;
    overflow: hidden;
}
hr{
    border-color: rgba(255,255,255,.09);
}
</style>
"""

# =========================================================
# Local storage helpers
# =========================================================
def get_local_storage():
    if LocalStorage is None:
        return None
    try:
        return LocalStorage()
    except Exception:
        return None


def ls_get(key, default=None):
    ls = get_local_storage()
    if ls is None:
        return default
    try:
        val = ls.getItem(LS_PREFIX + key, key=f"get_{key}")
        return default if val in (None, "", "null", "None") else val
    except Exception:
        return default


def ls_set(key, value):
    ls = get_local_storage()
    if ls is None:
        return
    try:
        ls.setItem(LS_PREFIX + key, str(value), key=f"set_{key}")
    except Exception:
        pass

# =========================================================
# Banco local
# =========================================================
def get_conn():
    return sqlite3.connect(DB, check_same_thread=False)


def init_db(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS upload_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_name TEXT NOT NULL,
            uploaded_at TEXT NOT NULL,
            total_rows INTEGER NOT NULL,
            qg09_rows INTEGER NOT NULL,
            falhas_rows INTEGER NOT NULL,
            status TEXT NOT NULL,
            message TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS raw_failures (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            upload_id INTEGER NOT NULL,
            cd_posto_cn TEXT,
            nr_wo TEXT,
            nr_serie TEXT,
            cd_modelo TEXT,
            modelo_corrigido TEXT,
            dt_hr_inspecao TEXT,
            anomalia_falha TEXT,
            posto_origem_falha TEXT,
            cd_user_inspecao TEXT
        )
        """
    )
    conn.commit()


def create_upload(conn, file_name, total_rows, qg09_rows, falhas_rows, status="PROCESSADO", message=""):
    cur = conn.execute(
        """
        INSERT INTO upload_log
        (file_name, uploaded_at, total_rows, qg09_rows, falhas_rows, status, message)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            file_name,
            datetime.now().isoformat(timespec="seconds"),
            int(total_rows),
            int(qg09_rows),
            int(falhas_rows),
            status,
            message,
        ),
    )
    conn.commit()
    return int(cur.lastrowid)


def save_raw(conn, upload_id, df):
    rows = []
    for _, row in df.iterrows():
        rows.append(
            (
                int(upload_id),
                str(row.get("CD_POSTO_CN", "")),
                str(row.get("NR_WO", "")),
                str(row.get("NR_SERIE", "")),
                str(row.get("CD_MODELO", "")),
                str(row.get("MODELO_CORRIGIDO", "")),
                row.get("DT_HR_INSPECAO").isoformat(sep=" ", timespec="seconds") if pd.notna(row.get("DT_HR_INSPECAO")) else None,
                str(row.get("ANOMALIA_FALHA", "")),
                str(row.get("POSTO_ORIGEM_FALHA", "")),
                str(row.get("CD_USER_INSPECAO", "")),
            )
        )
    conn.executemany(
        """
        INSERT INTO raw_failures
        (upload_id, cd_posto_cn, nr_wo, nr_serie, cd_modelo, modelo_corrigido, dt_hr_inspecao,
         anomalia_falha, posto_origem_falha, cd_user_inspecao)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    conn.commit()


def uploads_table(conn):
    return pd.read_sql_query(
        "SELECT id, file_name, uploaded_at, total_rows, qg09_rows, falhas_rows, status, message FROM upload_log ORDER BY id DESC LIMIT 300",
        conn,
    )


def delete_upload(conn, upload_id):
    conn.execute("DELETE FROM raw_failures WHERE upload_id=?", (int(upload_id),))
    conn.execute("DELETE FROM upload_log WHERE id=?", (int(upload_id),))
    conn.commit()


def delete_all(conn):
    conn.execute("DELETE FROM raw_failures")
    conn.execute("DELETE FROM upload_log")
    conn.commit()


def load_all_df(conn):
    df = pd.read_sql_query(
        """
        SELECT upload_id,
               cd_posto_cn AS CD_POSTO_CN,
               nr_wo AS NR_WO,
               nr_serie AS NR_SERIE,
               cd_modelo AS CD_MODELO,
               modelo_corrigido AS MODELO_CORRIGIDO,
               dt_hr_inspecao AS DT_HR_INSPECAO,
               anomalia_falha AS ANOMALIA_FALHA,
               posto_origem_falha AS POSTO_ORIGEM_FALHA,
               cd_user_inspecao AS CD_USER_INSPECAO
        FROM raw_failures
        ORDER BY dt_hr_inspecao, id
        """,
        conn,
    )
    if not df.empty:
        df["DT_HR_INSPECAO"] = pd.to_datetime(df["DT_HR_INSPECAO"], errors="coerce")
    return df

# =========================================================
# Leitura e tratamento
# =========================================================
def normalize_columns(df):
    out = df.copy()
    out.columns = [str(x).strip().replace("\ufeff", "") for x in out.columns]
    return out


def read_file(uploaded_file):
    ext = uploaded_file.name.lower().split(".")[-1]
    content = uploaded_file.getvalue()

    if ext == "csv":
        last_err = None
        for enc in ["utf-8-sig", "utf-16", "latin1"]:
            for sep in [None, "\t", ";", ","]:
                try:
                    if sep is None:
                        df = pd.read_csv(io.BytesIO(content), encoding=enc, sep=None, engine="python", dtype=str)
                    else:
                        df = pd.read_csv(io.BytesIO(content), encoding=enc, sep=sep, dtype=str)
                    return normalize_columns(df)
                except Exception as err:
                    last_err = err
        raise ValueError(f"Não foi possível ler o CSV. Detalhe: {last_err}")

    if ext in ["xlsx", "xls"]:
        engine = "openpyxl" if ext == "xlsx" else "xlrd"
        return normalize_columns(pd.read_excel(io.BytesIO(content), engine=engine, dtype=str))

    raise ValueError("Formato não suportado. Use .xlsx, .xls ou .csv")


def validate_df(df):
    missing = [c for c in REQ if c not in df.columns]
    return len(missing) == 0, missing


def parse_dt(series):
    dt = pd.to_datetime(series, errors="coerce")
    mask = dt.isna() & series.notna()
    if mask.any():
        dt.loc[mask] = pd.to_datetime(series[mask], errors="coerce", dayfirst=True)
    return dt


def norm_text(value):
    if pd.isna(value):
        return ""
    return str(value).strip()


def norm_posto(value):
    txt = norm_text(value).upper()
    if "QG09" in txt:
        return "QG09"
    return txt


def corrigir_modelo(value):
    txt = norm_text(value).upper()
    if txt == "":
        return "Não informado"
    return MAPA_MODELOS.get(txt, txt)


def prepare(df):
    work = df.copy()

    # Garante colunas opcionais para evitar erro na persistencia/filtros
    for col in OPTIONAL_COLS:
        if col not in work.columns:
            work[col] = ""

    work["CD_POSTO_CN"] = work["CD_POSTO_CN"].map(norm_posto)
    work["CD_MODELO"] = work["CD_MODELO"].map(lambda x: norm_text(x).upper())
    work["MODELO_CORRIGIDO"] = work["CD_MODELO"].map(corrigir_modelo)
    work["DT_HR_INSPECAO"] = parse_dt(work["DT_HR_INSPECAO"])
    work["ANOMALIA_FALHA"] = work["ANOMALIA_FALHA"].map(norm_text)
    work["POSTO_ORIGEM_FALHA"] = work["POSTO_ORIGEM_FALHA"].map(norm_text)
    work["NR_WO"] = work["NR_WO"].map(norm_text)
    work["NR_SERIE"] = work["NR_SERIE"].map(norm_text)
    work["CD_USER_INSPECAO"] = work["CD_USER_INSPECAO"].map(norm_text)

    # Filtro automatico QG09 e somente registros com falha preenchida
    qg09 = work[work["CD_POSTO_CN"].eq(POSTO_FIXO)].copy()
    qg09 = qg09[qg09["DT_HR_INSPECAO"].notna()].copy()
    with_failure = qg09[qg09["ANOMALIA_FALHA"].ne("")].copy()

    keep_cols = [
        "CD_POSTO_CN",
        "NR_WO",
        "NR_SERIE",
        "CD_MODELO",
        "MODELO_CORRIGIDO",
        "DT_HR_INSPECAO",
        "ANOMALIA_FALHA",
        "POSTO_ORIGEM_FALHA",
        "CD_USER_INSPECAO",
    ]
    return work, qg09[keep_cols], with_failure[keep_cols]

# =========================================================
# Pareto e filtros
# =========================================================
def apply_filters(df, modelos, origem, start_date, end_date):
    filt = df.copy()
    if modelos:
        filt = filt[filt["MODELO_CORRIGIDO"].isin(modelos)]
    if origem:
        filt = filt[filt["POSTO_ORIGEM_FALHA"].isin(origem)]
    if start_date and end_date:
        sdt = datetime.combine(start_date, time(0, 0, 0))
        edt = datetime.combine(end_date, time(23, 59, 59))
        filt = filt[(filt["DT_HR_INSPECAO"] >= sdt) & (filt["DT_HR_INSPECAO"] <= edt)]
    return filt


def make_pareto(df, column, top_n=10):
    if df.empty or column not in df.columns:
        return pd.DataFrame(columns=["Item", "Quantidade", "Percentual", "Percentual Acumulado"])

    s = df[column].fillna("").astype(str).str.strip()
    s = s[s.ne("")]
    if s.empty:
        return pd.DataFrame(columns=["Item", "Quantidade", "Percentual", "Percentual Acumulado"])

    resumo = s.value_counts().head(int(top_n)).reset_index()
    resumo.columns = ["Item", "Quantidade"]
    total = resumo["Quantidade"].sum()
    resumo["Percentual"] = resumo["Quantidade"] / total if total else 0
    resumo["Percentual Acumulado"] = resumo["Percentual"].cumsum()
    return resumo


def pareto_plot(resumo, titulo, x_title="Falha"):
    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            x=resumo["Item"],
            y=resumo["Quantidade"],
            name="Quantidade",
            marker=dict(color="#2f80ed", line=dict(color="rgba(255,255,255,.35)", width=1)),
            yaxis="y1",
            hovertemplate="%{x}<br>Quantidade: %{y}<extra></extra>",
        )
    )

    fig.add_trace(
        go.Scatter(
            x=resumo["Item"],
            y=resumo["Percentual Acumulado"],
            name="% acumulado",
            mode="lines+markers",
            line=dict(color="#ff3b30", width=3),
            marker=dict(size=8, color="#ff3b30"),
            yaxis="y2",
            hovertemplate="%{x}<br>Acumulado: %{y:.1%}<extra></extra>",
        )
    )

    # Linha de 80% do Pareto classico
    fig.add_hline(
        y=0.80,
        line_dash="dash",
        line_color="rgba(245,158,11,.85)",
        annotation_text="80%",
        annotation_position="top right",
        yref="y2",
    )

    fig.update_layout(
        title=dict(text=titulo, x=0.02, xanchor="left", font=dict(size=22, color="#ffffff")),
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(8,16,31,.85)",
        font=dict(color="#e8eefc"),
        xaxis=dict(title=x_title, tickangle=-25, showgrid=False),
        yaxis=dict(title="Quantidade", zeroline=False, gridcolor="rgba(255,255,255,.08)"),
        yaxis2=dict(
            title="% acumulado",
            overlaying="y",
            side="right",
            tickformat=".0%",
            range=[0, 1.05],
            showgrid=False,
        ),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        bargap=0.22,
        height=560,
        margin=dict(l=40, r=40, t=80, b=120),
    )
    return fig


def format_int(v):
    try:
        return f"{int(v):,}".replace(",", ".")
    except Exception:
        return "0"


def pct(v):
    try:
        return f"{float(v)*100:.1f}%".replace(".", ",")
    except Exception:
        return "0,0%"


def kpi(label, value, sub=""):
    return f"""
    <div class="kpi-card">
        <div class="kpi-label">{label}</div>
        <div class="kpi-value">{value}</div>
        <div class="kpi-sub">{sub}</div>
    </div>
    """


def section_header(title, sub=""):
    st.markdown(
        f"""
        <div class="section-card">
            <div class="section-title">{title}</div>
            <div class="section-sub">{sub}</div>
        """,
        unsafe_allow_html=True,
    )


def section_close():
    st.markdown("</div>", unsafe_allow_html=True)

# =========================================================
# Main
# =========================================================
def main():
    conn = get_conn()
    init_db(conn)

    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown(
        f"""
        <div class="main-title">
            <h1>Pareto de Falhas QG09</h1>
            <p>Upload de base operacional, correção automática de modelos e Pareto clássico Top 10 em Plotly · {APP_VERSION}</p>
            <div style="margin-top:12px">
                <span class="badge">Filtro fixo: QG09</span>
                <span class="badge">Pareto clássico</span>
                <span class="badge">Modelos corrigidos automaticamente</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.sidebar:
        st.subheader("Configurações")
        top_n = st.slider("Top N", min_value=5, max_value=25, value=int(ls_get("top_n", 10)), step=1)
        ls_set("top_n", top_n)
        st.caption("O Pareto principal usa ANOMALIA_FALHA e filtro automático CD_POSTO_CN = QG09.")
        st.divider()
        st.markdown("**Mapeamento automático de modelos**")
        for k, v in MAPA_MODELOS.items():
            st.caption(f"{k} → {v}")

    tabs = st.tabs(["Dashboard", "Pareto por Modelo", "Origem da Falha", "Base & Upload", "Histórico", "Sobre"])
    df_all = load_all_df(conn)

    # ------------------------------
    # Upload
    # ------------------------------
    with tabs[3]:
        section_header("Base & Upload", "Carregue a base Excel/CSV. O sistema filtra QG09, corrige modelos e mantém somente falhas preenchidas.")
        uploaded = st.file_uploader("Base operacional (.xlsx, .xls ou .csv)", type=["xlsx", "xls", "csv"])
        prepared = None
        raw = None
        qg09 = None

        if uploaded is not None:
            try:
                raw = read_file(uploaded)
                ok, missing = validate_df(raw)
                if not ok:
                    st.error("Base inválida. Colunas obrigatórias ausentes: " + ", ".join(missing))
                else:
                    original, qg09, prepared = prepare(raw)
                    st.success(
                        f"Arquivo carregado: {uploaded.name} | Linhas originais: {len(original)} | QG09: {len(qg09)} | Falhas QG09: {len(prepared)}"
                    )
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Linhas originais", format_int(len(original)))
                    c2.metric("Linhas QG09", format_int(len(qg09)))
                    c3.metric("Falhas QG09", format_int(len(prepared)))

                    st.markdown("**Prévia da base tratada**")
                    st.dataframe(prepared.head(200), use_container_width=True, hide_index=True)

                    resumo_modelos = prepared["MODELO_CORRIGIDO"].value_counts().reset_index()
                    resumo_modelos.columns = ["MODELO_CORRIGIDO", "Quantidade"]
                    st.markdown("**Resumo por modelo corrigido**")
                    st.dataframe(resumo_modelos, use_container_width=True, hide_index=True)
            except Exception as err:
                st.error(f"Erro ao ler a base: {err}")

        col_a, col_b = st.columns([1, 1])
        with col_a:
            if st.button("Salvar arquivo localmente", type="primary", use_container_width=True):
                if uploaded is None or prepared is None:
                    st.error("Selecione e valide um arquivo antes de salvar.")
                elif prepared.empty:
                    st.error("A base foi lida, mas não há falhas QG09 para salvar.")
                else:
                    uid = create_upload(
                        conn,
                        uploaded.name,
                        total_rows=len(raw),
                        qg09_rows=len(qg09),
                        falhas_rows=len(prepared),
                        message="Base tratada e salva localmente.",
                    )
                    save_raw(conn, uid, prepared)
                    st.success(f"Upload {uid} salvo com sucesso.")
                    st.rerun()
        with col_b:
            if st.button("Limpar toda a base local", use_container_width=True):
                delete_all(conn)
                st.success("Base local limpa.")
                st.rerun()
        section_close()

    # Dados disponíveis para dashboards
    df_all = load_all_df(conn)

    # ------------------------------
    # Filtros globais se houver dados
    # ------------------------------
    if df_all.empty:
        with tabs[0]:
            st.info("Sem dados salvos ainda. Faça upload na aba Base & Upload.")
        with tabs[1]:
            st.info("Sem dados salvos ainda. Faça upload na aba Base & Upload.")
        with tabs[2]:
            st.info("Sem dados salvos ainda. Faça upload na aba Base & Upload.")
    else:
        min_d = df_all["DT_HR_INSPECAO"].dt.date.min()
        max_d = df_all["DT_HR_INSPECAO"].dt.date.max()

        with st.sidebar:
            st.divider()
            st.subheader("Filtros do Pareto")
            start_date, end_date = st.date_input(
                "Período",
                value=(min_d, max_d),
                min_value=min_d,
                max_value=max_d,
                format="DD/MM/YYYY",
            )
            modelos_opts = sorted([x for x in df_all["MODELO_CORRIGIDO"].dropna().unique().tolist() if x])
            modelos_sel = st.multiselect("Modelo corrigido", modelos_opts, default=[])
            origem_opts = sorted([x for x in df_all["POSTO_ORIGEM_FALHA"].dropna().unique().tolist() if x])
            origem_sel = st.multiselect("Posto origem da falha", origem_opts, default=[])

        filt = apply_filters(df_all, modelos_sel, origem_sel, start_date, end_date)
        pareto_falhas = make_pareto(filt, "ANOMALIA_FALHA", top_n=top_n)

        # ------------------------------
        # Dashboard
        # ------------------------------
        with tabs[0]:
            total_falhas = len(filt)
            falha_top = pareto_falhas.loc[0, "Item"] if not pareto_falhas.empty else "Sem dados"
            qtd_top = pareto_falhas.loc[0, "Quantidade"] if not pareto_falhas.empty else 0
            modelo_top = filt["MODELO_CORRIGIDO"].value_counts().idxmax() if not filt.empty else "Sem dados"
            top10_acc = pareto_falhas["Percentual Acumulado"].iloc[-1] if not pareto_falhas.empty else 0

            c1, c2, c3, c4 = st.columns(4)
            c1.markdown(kpi("Falhas QG09", format_int(total_falhas), "Após filtros aplicados"), unsafe_allow_html=True)
            c2.markdown(kpi("Modelo mais afetado", modelo_top, "Maior volume no recorte"), unsafe_allow_html=True)
            c3.markdown(kpi("Falha Top 1", format_int(qtd_top), falha_top[:80]), unsafe_allow_html=True)
            c4.markdown(kpi("Acumulado Top", pct(top10_acc), f"Top {top_n} no recorte"), unsafe_allow_html=True)

            section_header("Pareto clássico de falhas - Top 10", "Barras = quantidade de falhas. Linha vermelha = percentual acumulado. Linha pontilhada = referência de 80%.")
            if pareto_falhas.empty:
                st.warning("Não há dados para o Pareto no filtro selecionado.")
            else:
                st.plotly_chart(pareto_plot(pareto_falhas, f"Pareto de Falhas QG09 - Top {top_n}"), use_container_width=True)
                show = pareto_falhas.copy()
                show["Percentual"] = show["Percentual"].map(pct)
                show["Percentual Acumulado"] = show["Percentual Acumulado"].map(pct)
                st.dataframe(show, use_container_width=True, hide_index=True)
            section_close()

        # ------------------------------
        # Pareto por modelo
        # ------------------------------
        with tabs[1]:
            section_header("Pareto por Modelo", "Selecione um modelo corrigido para analisar o Top de falhas dentro dele.")
            modelo_default = modelos_opts[0] if modelos_opts else None
            modelo_focus = st.selectbox("Modelo para análise", modelos_opts, index=0 if modelos_opts else None)
            if modelo_focus:
                df_modelo = filt[filt["MODELO_CORRIGIDO"].eq(modelo_focus)]
                p_modelo = make_pareto(df_modelo, "ANOMALIA_FALHA", top_n=top_n)
                if p_modelo.empty:
                    st.warning("Sem dados para o modelo selecionado no filtro atual.")
                else:
                    st.plotly_chart(pareto_plot(p_modelo, f"Pareto de Falhas - {modelo_focus} - Top {top_n}"), use_container_width=True)
                    show = p_modelo.copy()
                    show["Percentual"] = show["Percentual"].map(pct)
                    show["Percentual Acumulado"] = show["Percentual Acumulado"].map(pct)
                    st.dataframe(show, use_container_width=True, hide_index=True)
            section_close()

        # ------------------------------
        # Origem da falha
        # ------------------------------
        with tabs[2]:
            section_header("Pareto por Origem da Falha", "Ranking dos postos/origens que mais concentram falhas no QG09.")
            p_origem = make_pareto(filt, "POSTO_ORIGEM_FALHA", top_n=top_n)
            if p_origem.empty:
                st.warning("Sem dados de origem da falha no filtro selecionado.")
            else:
                st.plotly_chart(pareto_plot(p_origem, f"Pareto de Origem da Falha - Top {top_n}", x_title="Origem da falha"), use_container_width=True)
                show = p_origem.copy()
                show["Percentual"] = show["Percentual"].map(pct)
                show["Percentual Acumulado"] = show["Percentual Acumulado"].map(pct)
                st.dataframe(show, use_container_width=True, hide_index=True)
            section_close()

    # ------------------------------
    # Historico
    # ------------------------------
    with tabs[4]:
        section_header("Histórico de Uploads", "Auditoria dos arquivos processados localmente.")
        hist = uploads_table(conn)
        if hist.empty:
            st.info("Os uploads processados aparecerão aqui.")
        else:
            st.dataframe(hist, use_container_width=True, hide_index=True)
            selected_id = st.selectbox("Selecionar upload", hist["id"].tolist(), format_func=lambda x: f"Upload {x}")
            if st.button("Excluir upload selecionado", use_container_width=True):
                delete_upload(conn, selected_id)
                st.success("Upload excluído com sucesso.")
                st.rerun()
        section_close()

    # ------------------------------
    # Sobre
    # ------------------------------
    with tabs[5]:
        section_header("Sobre", "Site de Pareto QG09 inspirado no padrão visual do RFT, com gráfico clássico em Plotly.")
        st.markdown(
            """
            **Regras principais**

            - O sistema filtra automaticamente `CD_POSTO_CN = QG09`.
            - O Pareto principal usa `ANOMALIA_FALHA`.
            - Linhas sem `ANOMALIA_FALHA` preenchida não entram no Pareto.
            - A coluna `MODELO_CORRIGIDO` é criada automaticamente.

            **Mapeamento dos modelos no site**

            ```text
            VTBAGFC  -> VTBA
            V2MFGFC  -> V2 MF
            V2VTGFC  -> V2 VT
            G7GFCAN  -> G7
            G8GFCAN  -> G8
            ```

            **Como publicar no GitHub + Streamlit Cloud**

            1. Crie um repositório no GitHub.
            2. Envie `app.py`, `requirements.txt`, `README.md` e a pasta `.streamlit`.
            3. No Streamlit Cloud, selecione o repositório e aponte para `app.py`.
            4. Clique em Deploy.
            """
        )
        section_close()


if __name__ == "__main__":
    main()
