# Pareto QG09 - V0.14

Versão V0.14 corrige o erro `ValueError: The truth value of a Series is ambiguous` e mantém o visual escuro corporativo inspirado na AGCO.

## Ajustes

- Correção definitiva no cálculo do gráfico Top 10 usando `total=float(g["Quantidade"].sum())`.
- Remoção de coluna duplicada `Quantidade` no dataframe do ranking.
- Visual escuro com alto contraste: fundo preto/grafite, vermelho AGCO e textos claros.
- Cabeçalho com espaço para logotipo oficial. Se você colocar `agco_logo.png` no repositório, o app carrega automaticamente; se não existir, aparece um wordmark textual `AGCO`.

## Deploy

Use como Main file path:

```text
app_V0_14.py
```
