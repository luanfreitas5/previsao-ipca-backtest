# Model Card — LightGBM direto com lags v0.1.0

**Status:** DRAFT
**Bloqueios pendentes:** `run_id` do MLflow e Git SHA (bloqueiam a rastreabilidade do número publicado); IC 95% por subperíodo (bloqueia afirmações por período); licença dos dados (bloqueia redistribuição dos dados).

## 1. Detalhes do modelo
- **Responsável / contato:** Luan Freitas — luan.mgf@gmail.com
- **Data:** 2026-10-26
- **Algoritmo:** LightGBM (API nativa), estratégia **direta**: um modelo por horizonte (1, 2, 3, 6, 12 meses), com 12 defasagens de cada série (IPCA, IGP-M, Meta Selic, câmbio, IBC-Br). Hiperparâmetros em `configs/model_params.yaml`, sem ajuste fino. Reajustado a cada origem (janela expansiva); não há modelo final único.
- **Rastreabilidade:** Git SHA `TODO(owner): SHA do commit que gerou reports/relatorio_final.md` · MLflow run `TODO(owner): run_id do run pai "walk_forward"` · hash dos dados `ver tag data_hash do run; SHA-256 dos brutos em reports/datasheets/`
- **Licença:** MIT (código)

## 2. Uso pretendido
- **Uso primário:** testar se variáveis macro públicas (IGP-M, Selic, câmbio, IBC-Br) melhoram a previsão do IPCA em relação ao AutoARIMA e ao Focus.
- **Usuários pretendidos:** estudantes e pesquisadores; revisores do portfólio.
- **Humano no circuito:** sim. Experimento de pesquisa, sem decisão automatizada.

## 3. Usos fora do escopo
- Decisões de investimento, precificação, reajuste de contratos ou política monetária.
- Outros países, outras séries ou frequências: não validado.
- Horizontes acima de 12 meses: não avaliado.
- Usar como substituto do AutoARIMA ou do Focus: no backtest ele perde para ambos.

## 4. Fatores
- **Grupos relevantes:** não há grupos de pessoas. Fatores: horizonte e subperíodo do mês-alvo.
- **Ambientes:** séries nacionais do SGS na revisão mais recente; informação restrita a `available_at <= t0`.

## 5. Métricas
- **Métrica principal:** RMSE em p.p. do IPCA mensal com IC 95% por bootstrap em blocos (penaliza choques grandes); MAE como secundária. Regressão: sem custo assimétrico de FP/FN.
- **Limiar de decisão:** não se aplica (previsão pontual). Intervalos conformais de 90%.
- **Calibração:** cobertura empírica dos intervalos conformais (nominal 90%): 0,85 em h=1 e 0,81 em h=12 — subcobre. Figura: `reports/figures/cobertura_conformal.png`.

## 6. Dados de avaliação
Mesmo protocolo do AutoARIMA: origens mensais desde 2010-01-31, janela expansiva, amostra comum (n = 200 em h=1; 189 em h=12), snapshot de 2026-10-21, avaliação interna sem validação externa. O treino só usa linhas cujo alvo já foi divulgado (`tests/test_leakage.py`).

## 7. Dados de treino
Cinco séries do BCB/SGS desde 2000-01. Ver [Datasheet BCB/SGS](../datasheets/bcb_sgs.md). O Focus não entra como feature.

## 8. Análise quantitativa
RMSE (p.p.) com IC 95% por bootstrap em blocos. Baselines: ingênuo (último valor) e Focus.

| Recorte | n | RMSE LightGBM (IC 95%) | Ingênuo (último valor) | Focus |
|---|---|---|---|---|
| Geral, h=1 | 200 | 0,363 (0,316–0,409) | 0,412 (0,366–0,456) | 0,257 (0,220–0,293) |
| Geral, h=12 | 189 | 0,424 (0,354–0,497) | 0,482 (0,398–0,564) | 0,356 (0,267–0,443) |
| 2010–2015, h=1 | 71 | 0,286 | 0,324 | 0,184 |
| 2016–2019, h=1 | 48 | 0,340 | 0,422 | 0,251 |
| 2020–2022, h=1 | 36 | 0,556 | 0,577 | 0,423 |
| 2023+, h=1 | 45 | 0,295 | 0,363 | 0,170 |
| 2010–2015, h=12 | 60 | 0,294 | 0,287 | 0,255 |
| 2016–2019, h=12 | 48 | 0,470 | 0,496 | 0,319 |
| 2020–2022, h=12 | 36 | 0,612 | 0,711 | 0,580 |
| 2023+, h=12 | 45 | 0,322 | 0,448 | 0,260 |

Subperíodos sem IC (`TODO(owner): bootstrap por fatia`). Fonte: `reports/tables/metricas_por_horizonte.csv` e `metricas_por_periodo.csv`. Em 2010–2015, h=12, o LightGBM (0,294) ficou **pior** que o ingênuo (0,287).

**Significância contra o Focus (Diebold-Mariano, correção HLN):** perde de forma significativa em todos os horizontes (h=1: p < 0,001; h≥2: p entre 0,010 e 0,038 na perda quadrática, e entre 0,001 e 0,024 na absoluta). Não supera o AutoARIMA apesar das variáveis adicionais.

## 9. Considerações éticas e fairness
- Atributos sensíveis auditados: nenhum; dados macroeconômicos agregados, sem pessoas.
- Disparidades encontradas: não se aplica.
- Mitigação aplicada: nenhuma.
- Base legal LGPD: não se aplica.

## 10. Limitações, riscos e monitoramento
- **Limitações conhecidas:**
  - Perde para o Focus e para o AutoARIMA; o ganho esperado das variáveis extras não apareceu.
  - Vintages: IBC-Br dessazonalizado é revisado; o SGS entrega a revisão mais recente, o que pode torná-lo levemente otimista como feature.
  - Atrasos de divulgação constantes (aproximação conservadora do calendário real).
  - Amostra curta e erros autocorrelacionados; sem ajuste fino de hiperparâmetros.
  - Intervalos conformais subcobrem.
- **Mudanças de distribuição previstas:** choque 2020–2022; regime de juros e câmbio muda a relação entre as features e o IPCA.
- **Monitoramento:** sem implantação, sem monitoramento. Se implantado: RMSE em janela móvel contra o Focus e o AutoARIMA, mensal.
- **Critério de retreino / descontinuação:** reajustado a cada origem. Descontinuar se o RMSE em h=1 em dados novos ficar acima do ingênuo (0,412).
