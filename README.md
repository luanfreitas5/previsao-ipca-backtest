# 📈 Previsão do IPCA com backtest walk-forward

[![CI](https://github.com/luanfreitas5/previsao-ipca-backtest/actions/workflows/ci.yml/badge.svg)](https://github.com/luanfreitas5/previsao-ipca-backtest/actions/workflows/ci.yml)
[![Tests](https://github.com/luanfreitas5/previsao-ipca-backtest/actions/workflows/tests.yml/badge.svg)](https://github.com/luanfreitas5/previsao-ipca-backtest/actions/workflows/tests.yml)
[![Docs](https://github.com/luanfreitas5/previsao-ipca-backtest/actions/workflows/docs.yml/badge.svg)](https://luanfreitas5.github.io/previsao-ipca-backtest/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](pyproject.toml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

Previsão do **IPCA mensal** com backtest **walk-forward sem vazamento temporal**, comparada
ao **Boletim Focus** do Banco Central, com testes estatísticos, intervalos conformais e
rastreamento de experimentos.

## 🎯 Problema

Avaliar modelos de previsão de inflação costuma ser enganoso: usar séries na versão final
(ignorando a data de divulgação), treinar com alvos ainda desconhecidos ou comparar modelos em
amostras diferentes produz erros artificialmente baixos. Este projeto trata o vazamento temporal
como requisito de projeto, com testes automatizados que o verificam.

## ❓ Pergunta

> Algum modelo estatístico ou de machine learning, usando apenas informação **publicamente
> disponível na data da previsão**, consegue superar de forma estatisticamente significativa a
> mediana do Focus na previsão do IPCA mensal — e em quais horizontes e períodos ele perde?

## 🗂️ Dados

| Fonte | Série | Código SGS | Uso | Atraso de divulgação assumido |
|---|---|---|---|---|
| BCB/SGS | IPCA, variação mensal (%) | 433 | alvo e lags | 10 dias após o fim do mês |
| BCB/SGS | IGP-M, variação mensal (%) | 189 | feature | 0 dia |
| BCB/SGS | Meta Selic (% a.a.) | 432 | feature (último valor do mês) | 0 dia |
| BCB/SGS | Dólar comercial (R$/US$) | 1 | feature (variação % da média mensal) | 0 dia |
| BCB/SGS | IBC-Br dessazonalizado | 24364 | feature (variação % mensal) | 50 dias |
| BCB/Olinda | Expectativas Focus (IPCA mensal) | — | baseline | snapshot + 3 dias |

Os dados brutos **não ficam no Git**: o `make ingest` baixa e guarda snapshots datados e
imutáveis em `data/bronze/<fonte>/<AAAA-MM-DD>/` com manifesto SHA-256. Rodar de novo no mesmo
dia usa o cache local (idempotente). Os atrasos de divulgação ficam em
[`configs/series.yaml`](configs/series.yaml).

Camadas: `bronze` (como recebido) → `silver` (tipado, deduplicado, validado com pandera) →
`gold` (ledger point-in-time, tabela supervisionada e previsões).

## 🧪 Método

1. **Features point-in-time.** Na origem `o` (fim de mês), só entram observações com
   `available_at <= o`. Testes ([`tests/test_leakage.py`](tests/test_leakage.py)) alteram os
   valores futuros e exigem que as features não mudem.
2. **Modelos.** Ingênuo (último valor e sazonal), AutoARIMA e AutoETS (statsforecast) e
   LightGBM direto (um modelo por horizonte) com 12 lags de cada série.
3. **Backtest.** Janela expansiva, reajuste a cada origem, horizontes 1, 2, 3, 6 e 12 meses.
   O treino só usa linhas cujo **alvo já havia sido divulgado**; `assert_no_leakage` barra o
   contexto que violar isso.
4. **Avaliação.** MAE e RMSE por horizonte na amostra comum, IC de 95% por bootstrap em blocos,
   fatias por subperíodo, piores erros e teste de **Diebold-Mariano** (correção HLN) contra o Focus.
5. **Incerteza.** Intervalos conformais de 90% calibrados só com erros já observáveis.
6. **Experimentos.** MLflow: run pai com configuração, SHA do git e hashes dos dados; run filho por modelo.

## 🔁 Como reproduzir

Requisitos: Python 3.10+ e [uv](https://docs.astral.sh/uv/).

```bash
make init        # instala dependências e hooks do pre-commit
make ingest      # baixa SGS + Focus para data/bronze (idempotente)
make silver      # bronze -> silver
make gold        # ledger point-in-time + tabela supervisionada
make backtest    # walk-forward + conformal + MLflow
make report      # tabelas, figuras e reports/relatorio_final.md
# ou tudo de uma vez:
make pipeline
make mlflow      # interface do MLflow em http://localhost:5000
```

Qualidade e testes: `make test` (testes), `make quality` (ruff, basedpyright, bandit, vulture,
xenon, interrogate, refurb) e `make check` (tudo, espelhando o CI).

## 📊 Resultados

Os resultados são **gerados** pelo pipeline e dependem da data da coleta (o Focus e o IPCA são
atualizados todo mês). Depois de `make report`, consulte:

- [`reports/relatorio_final.md`](reports/relatorio_final.md) — tabelas, testes de Diebold-Mariano,
  fatias por período e a seção **“Onde os modelos perdem para o Focus”**;
- `reports/figures/` — RMSE por horizonte, previsto vs. realizado e cobertura conformal;
- `reports/tables/` — as mesmas tabelas em CSV.

> Nenhum número foi registrado neste README de propósito: ele só deve citar resultados que o
> relatório gerado sustente.

## ⚠️ Limitações

- **Vintages.** O SGS expõe a revisão mais recente das séries, não a versão que existia em cada
  data. O IPCA quase não é revisado, mas o IBC-Br dessazonalizado é; isso pode tornar o IBC-Br
  levemente otimista.
- **Calendário de divulgação.** Os atrasos são aproximações conservadoras (constantes), não o
  calendário real de cada mês.
- **Amostra curta.** Dezenas de observações por horizonte: leia sempre os ICs e os p-valores.
  Horizontes longos têm erros muito autocorrelacionados (menos informação independente).
- **Conformal.** A cobertura nominal assume resíduos trocáveis; choques (2020–2022) a violam.
- **Focus.** Usa-se a mediana com `baseCalculo = 0` (últimos 30 dias); outras estatísticas
  ou janelas podem mudar o resultado.
- **Sem ajuste fino de hiperparâmetros**, por escolha, para não otimizar sobre o período de teste.

## 🧱 Estrutura

```
configs/      YAML validados com Pydantic (séries, atrasos, modelos, caminhos)
data/         bronze (imutável) | silver (limpo) | gold (modelagem) — fora do Git
src/          config, data, features, models, backtest, reporting, experiment, schemas, ...
tests/        unitários, property-based (hypothesis) e testes de vazamento
notebooks/    EDA (01_eda.ipynb)
reports/      relatório final, figuras e tabelas
docs/         MkDocs Material + mkdocstrings
```

## 📄 Licença

[MIT](LICENSE)
