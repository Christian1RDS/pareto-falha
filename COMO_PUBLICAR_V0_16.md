# Como publicar a versão V0.16

## Arquivos que você deve subir no GitHub

Suba estes arquivos na raiz do repositório:

```text
app_V0_16.py
requirements.txt
README_V0_16.md
.gitignore
```

Se você estiver usando a configuração visual do Streamlit, suba também:

```text
.streamlit/config.toml
```

> Observação: se você estiver subindo os arquivos manualmente pelo GitHub, crie uma pasta chamada `.streamlit` e coloque dentro dela o arquivo `config.toml`.

---

## Arquivo principal no Streamlit Cloud

No campo **Main file path**, use exatamente:

```text
app_V0_16.py
```

---

## Logo oficial da AGCO

Para o logo aparecer no cabeçalho do site, coloque o arquivo da logo oficial da AGCO na raiz do repositório.

A V0.16 aceita qualquer um destes nomes:

```text
agco_logo.png
AGCO_logo.png
agco-logo.png
logo_agco.png
logo.png
AGCO.png
agco.png
agco_corporate_logo.png
AGCO_Corporate_Logo.png
```

Exemplo recomendado:

```text
agco_logo.png
```

A estrutura final pode ficar assim:

```text
pareto-falha/
├── app_V0_16.py
├── requirements.txt
├── README_V0_16.md
├── .gitignore
├── agco_logo.png
└── .streamlit/
    └── config.toml
```

---

## Passo a passo no Streamlit Cloud

1. Acesse o Streamlit Cloud.
2. Abra o aplicativo do repositório `pareto-falha`.
3. Clique em **Manage app**.
4. Em **Main file path**, coloque:

```text
app_V0_16.py
```

5. Salve as alterações.
6. Clique em **Reboot app** ou **Rerun**.

---

## Se o logo não aparecer

Confira estes pontos:

1. O arquivo do logo está na **raiz do repositório**, junto do `app_V0_16.py`.
2. O nome do arquivo está exatamente em um dos nomes aceitos.
3. A extensão está correta, preferencialmente `.png`.
4. Depois de subir o logo, faça **Reboot app** no Streamlit Cloud.

---

## Observação importante

A aplicação procura o logo automaticamente. Se nenhum arquivo de logo for encontrado, o cabeçalho mostra o texto:

```text
AGCO Corporation
```

Isso não é erro; é apenas o fallback visual da aplicação.
