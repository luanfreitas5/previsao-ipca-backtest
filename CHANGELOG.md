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
