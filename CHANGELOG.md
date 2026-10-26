# Changelog

Todas as mudanças relevantes deste projeto são documentadas aqui.
Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e versionamento
[SemVer](https://semver.org/lang/pt-BR/).

## [Unreleased]

### Adicionado
- Ingestão idempotente das séries SGS (IPCA, IGP-M, Selic, câmbio, IBC-Br) e do Focus, com
  snapshots datados e manifesto SHA-256 na camada bronze.
- Ledger point-in-time com data de divulgação por série e testes de ausência de vazamento.
- Modelos: ingênuo (último valor e sazonal), AutoARIMA, AutoETS e LightGBM direto com lags.
- Backtest walk-forward com janela expansiva, MAE/RMSE por horizonte com IC (bootstrap em blocos)
  e teste de Diebold-Mariano contra o Focus.
- Intervalos conformais calibrados apenas com erros já divulgados e rastreamento com MLflow.
- Relatório final automático em `reports/relatorio_final.md`.
- `Dockerfile` (job em lote, multi-stage, usuário não-root, dependências do `uv.lock`) e `.dockerignore` em lista de permissão.
- Model Cards (`reports/model_cards/`) do AutoARIMA e do LightGBM e Datasheets (`reports/datasheets/`) do BCB/SGS e do Focus.
- Tags de linhagem `git_dirty`, `data_hash` e `seed` nos runs do MLflow (pai e filhos); limites do IC do RMSE como métricas.
- Alvos `docker-build`, `docker-run`, `train`, `reproduce` e `format` no Makefile.

### Alterado
- Logging passou a usar `logging.config.dictConfig` com `configs/logging.yaml` (módulo `config.logging`, rotação diária à meia-noite, console compartilhado com as barras de progresso).
- `pyproject.toml` com grupos de dependências `dev`, `quality` e `docs`; `make lint` apenas verifica (use `make format` para corrigir).
- README reescrito no formato de portfólio (resultado com IC e baseline na primeira tela).
