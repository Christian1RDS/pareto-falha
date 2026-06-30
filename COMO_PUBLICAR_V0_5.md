# Como publicar a versão V0.5

Esta versão foi refeita com arquivos versionados.

## Arquivos versionados

```text
app_V0_5.py
requirements_V0_5.txt
README_V0_5.md
gitignore_V0_5.txt
streamlit_config_V0_5.toml
```

## Deploy no Streamlit Cloud

No campo **Main file path**, use:

```text
app_V0_5.py
```

## Importante sobre requirements

O Streamlit Cloud normalmente procura o arquivo:

```text
requirements.txt
```

Como você quer arquivos versionados, eu gerei `requirements_V0_5.txt`.

Para o deploy funcionar, faça uma destas opções:

1. Renomeie `requirements_V0_5.txt` para `requirements.txt` no GitHub; ou
2. Suba os dois: `requirements_V0_5.txt` e uma cópia chamada `requirements.txt`.

A V0.5 não usa Plotly, então o erro `ModuleNotFoundError: plotly` não deve acontecer.
