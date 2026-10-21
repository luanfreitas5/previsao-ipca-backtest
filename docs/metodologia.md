# Metodologia

## Informação disponível (point-in-time)

Cada observação mensal tem `available_at = fim do mês de referência + atraso de divulgação`
(`configs/series.yaml`). Na origem `o` (um fim de mês), um modelo só enxerga observações com
`available_at <= o`. O mesmo vale para o Focus: um snapshot de data `d` só é público a partir de
`d + 3 dias`.

## Horizonte e passos à frente

A origem é o último dia do mês `t`; o horizonte `h` é o mês `t + h`. Como o IPCA de `t` só sai
por volta do dia 10 de `t + 1`, o último dado conhecido é o de `t - 1`, logo o alvo está a
`h + 1` passos do último dado. Os modelos univariados usam essa contagem; o LightGBM recebe
`steps_ahead` como feature.

## Janela expansiva sem vazamento

A cada origem os modelos são reajustados com tudo o que era público. Para treino supervisionado,
entra apenas a linha cujo **alvo** já havia sido divulgado (`target_available_at <= o`). O motor
(`backtest.walk_forward.assert_no_leakage`) falha com `LeakageError` se o contexto violar isso.

## Avaliação

- MAE e RMSE por horizonte na amostra comum a todos os modelos e ao Focus.
- IC de 95% por bootstrap em blocos (bloco = horizonte), que preserva a autocorrelação dos erros.
- Diebold-Mariano contra o Focus com correção de Harvey-Leybourne-Newbold e cauda t.
- Fatias por subperíodo para mostrar onde os modelos perdem.

## Intervalos conformais

Calibrados, para cada (modelo, horizonte), com os erros absolutos de previsões anteriores cujo
alvo já foi divulgado na origem. A garantia de cobertura assume resíduos aproximadamente
trocáveis, o que séries temporais violam em parte.
