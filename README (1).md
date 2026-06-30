# Pareto de Falhas QG09 - Streamlit

Site em **Streamlit** para gerar **Pareto clássico de falhas QG09** com upload de Excel/CSV.

## Funções principais

- Upload de arquivos `.xlsx`, `.xls` e `.csv`.
- Filtro automático para `CD_POSTO_CN = QG09`.
- Correção automática dos modelos via coluna `MODELO_CORRIGIDO`.
- Pareto clássico em Plotly:
  - barras = quantidade;
  - linha vermelha = percentual acumulado;
  - eixo esquerdo = quantidade;
  - eixo direito = percentual acumulado;
  - linha de referência em 80%.
- Dashboard com cards e filtros.
- Pareto geral de falhas, Pareto por modelo e Pareto por origem da falha.
- Histórico local de uploads via SQLite.

## Mapeamento automático dos modelos

```text
VTBAGFC  -> VTBA
V2MFGFC  -> V2 MF
V2VTGFC  -> V2 VT
G7GFCAN  -> G7
G8GFCAN  -> G8
```

## Colunas obrigatórias na base

```text
CD_POSTO_CN
CD_MODELO
DT_HR_INSPECAO
ANOMALIA_FALHA
```

## Colunas opcionais usadas se existirem

```text
NR_WO
NR_SERIE
POSTO_ORIGEM_FALHA
CD_USER_INSPECAO
C_DPU_QG_AMARELO
```

## Como rodar localmente

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Como publicar no GitHub + Streamlit Cloud

1. Crie um repositório no GitHub.
2. Envie estes arquivos:
   - `app.py`
   - `requirements.txt`
   - `README.md`
   - `.streamlit/config.toml`
3. Acesse o Streamlit Cloud.
4. Clique em **New app**.
5. Selecione o repositório.
6. Em **Main file path**, use:

```text
app.py
```

7. Clique em **Deploy**.

## Observação

O banco `pareto_qg09_local.db` é criado automaticamente quando o app roda. Não é necessário subir esse arquivo para o GitHub.
