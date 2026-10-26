# Model Card — AutoARIMA (statsforecast) v0.1.0

**Status:** DRAFT
**Bloqueios pendentes:** `run_id` do MLflow e Git SHA (bloqueiam a rastreabilidade do número publicado); IC 95% por subperíodo (bloqueia a afirmação de que a diferença por período é robusta); licença dos dados (bloqueia redistribuição dos dados, não o uso do modelo).

## 1. Detalhes do modelo
- **Responsável / contato:** Luan Freitas — luan.mgf@gmail.com
- **Data:** 2026-10-26
- **Algoritmo:** AutoARIMA da biblioteca `statsforecast`, univariado sobre o IPCA mensal, com `season_length` de `configs/model_params.yaml`. Reajustado a cada origem do backtest (janela expansiva); não há modelo final único.
- **Rastreabilidade:** Git SHA `TODO(owner): SHA do commit que gerou reports/relatorio_final.md` · MLflow run `TODO(owner): run_id do run pai "walk_forward" (experimento previsao-ipca-backtest)` · hash dos dados `ver tag data_hash do run; SHA-256 dos brutos em reports/datasheets/`
- **Licença:** MIT (código)

## 2. Uso pretendido
- **Uso primário:** referência estatística univariada para estudar até onde o histórico do próprio IPCA prevê o IPCA dos próximos 1 a 12 meses, e como baseline de modelos com mais variáveis.
- **Usuários pretendidos:** estudantes e pesquisadores de séries temporais; revisores do portfólio.
- **Humano no circuito:** sim. É um experimento de pesquisa; nenhuma decisão automatizada depende da saída.

## 3. Usos fora do escopo
- Decisões de investimento, precificação, reajuste de contratos ou política monetária.
- Previsão de outros países, outras séries ou frequência diária/semanal: não validado.
- Horizontes acima de 12 meses: não avaliado.
- Substituir o Boletim Focus: no backtest, o Focus tem menor erro em todos os horizontes.

## 4. Fatores
- **Grupos relevantes:** não há grupos de pessoas. Os fatores relevantes são o **horizonte** (1, 2, 3, 6, 12 meses) e o **subperíodo** do mês-alvo (2010–2015, 2016–2019, 2020–2022, 2023+).
- **Ambientes:** série nacional do IPCA (SGS 433) na revisão mais recente; informação restrita ao que estava disponível na origem (`available_at <= t0`).

## 5. Métricas
- **Métrica principal:** RMSE em pontos percentuais do IPCA mensal, com IC 95% por bootstrap em blocos — penaliza mais os choques grandes, que são os erros mais custosos para quem usa a previsão para planejar; MAE como secundária. Não há custo assimétrico de FP/FN (regressão).
- **Limiar de decisão:** não se aplica (previsão pontual). Intervalos conformais de 90% calibrados só com erros já observáveis.
- **Calibração:** modelo pontual; no lugar de Brier, cobertura empírica dos intervalos conformais (nominal 90%): 0,84 em h=1 e 0,80 em h=12 — **subcobre**. Figura: `reports/figures/cobertura_conformal.png`.

## 6. Dados de avaliação
Backtest walk-forward com origens mensais desde 2010-01-31 (janela expansiva, reajuste a cada origem), amostra comum a todos os modelos e ao Focus: n = 200 origens em h=1 e 189 em h=12. Cada previsão usa só informação disponível na origem; o treino só inclui linhas cujo alvo já havia sido divulgado (verificado por `tests/test_leakage.py`). Snapshot dos dados de 2026-10-21. Avaliação **interna**; não há validação externa.

## 7. Dados de treino
Séries do IPCA do BCB/SGS desde 2000-01. Ver [Datasheet BCB/SGS](../datasheets/bcb_sgs.md). O Focus não é usado no treino; só como referência.

## 8. Análise quantitativa
RMSE (p.p.) com IC 95% por bootstrap em blocos. Baselines: ingênuo (último valor) e Focus.

| Recorte | n | RMSE AutoARIMA (IC 95%) | Ingênuo (último valor) | Focus |
|---|---|---|---|---|
| Geral, h=1 | 200 | 0,334 (0,294–0,377) | 0,412 (0,366–0,456) | 0,257 (0,220–0,293) |
| Geral, h=12 | 189 | 0,371 (0,309–0,441) | 0,482 (0,398–0,564) | 0,356 (0,267–0,443) |
| 2010–2015, h=1 | 71 | 0,251 | 0,324 | 0,184 |
| 2016–2019, h=1 | 48 | 0,363 | 0,422 | 0,251 |
| 2020–2022, h=1 | 36 | 0,484 | 0,577 | 0,423 |
| 2023+, h=1 | 45 | 0,264 | 0,363 | 0,170 |
| 2010–2015, h=12 | 60 | 0,271 | 0,287 | 0,255 |
| 2016–2019, h=12 | 48 | 0,373 | 0,496 | 0,319 |
| 2020–2022, h=12 | 36 | 0,558 | 0,711 | 0,580 |
| 2023+, h=12 | 45 | 0,287 | 0,448 | 0,260 |

Os subperíodos não têm IC calculado (`TODO(owner): bootstrap por fatia em reports/analysis`). Fonte: `reports/tables/metricas_por_horizonte.csv` e `metricas_por_periodo.csv`.

**Significância contra o Focus (Diebold-Mariano, correção HLN):** em h=1 o Focus vence com p < 0,001 (perdas quadrática e absoluta). Em h=6 e h=12 a diferença não é significativa (quadrática: p = 0,65 e 0,44; absoluta: p = 0,27 e 0,22). Em h=2 e h=3 depende da perda (quadrática: p = 0,06 e 0,10; absoluta: p = 0,023 em ambos). Ausência de significância não prova equivalência: os erros são autocorrelacionados e a amostra é curta.

**Pior erro:** jul/2022 (IPCA −0,68% observado; previsto ≈ +0,5 a +0,7 em h=1 a h=6) e mar/2022 (+1,62%): choques de política e de preços administrados que um modelo univariado não antecipa (`reports/tables/piores_erros.csv`).

## 9. Considerações éticas e fairness
- Atributos sensíveis auditados: nenhum. O modelo usa séries macroeconômicas agregadas; não há pessoas nem grupos protegidos nos dados.
- Disparidades encontradas: não se aplica.
- Mitigação aplicada: nenhuma.
- Base legal LGPD: não se aplica (sem dados pessoais).
- Risco ético relevante: uso indevido da previsão para decisões financeiras, ver seção 3.

## 10. Limitações, riscos e monitoramento
- **Limitações conhecidas:**
  - Perde para o Focus em todos os horizontes; empata estatisticamente em h=6 e h=12.
  - Vintages: o SGS expõe a revisão mais recente, não a versão da época (efeito pequeno no IPCA).
  - Amostra curta (≈190–200 origens por horizonte, com sobreposição); subperíodos com 36–71 origens.
  - Intervalos conformais subcobrem (0,80–0,89 conforme horizonte e modelo), consistente com a violação da trocabilidade em períodos de choque.
  - Sem ajuste fino de hiperparâmetros, por escolha, para não otimizar sobre o período de teste.
- **Mudanças de distribuição previstas:** choque de 2020–2022 (pandemia, combustíveis, preços administrados); é o período de maior erro para todos os modelos.
- **Monitoramento:** não há implantação, portanto não há monitoramento. Se for implantado: RMSE em janela móvel contra o Focus, mensal, ao divulgar cada IPCA.
- **Critério de retreino / descontinuação:** já é reajustado a cada origem. Descontinuar se, em dados novos, o RMSE de h=1 ficar acima do ingênuo (0,412).
