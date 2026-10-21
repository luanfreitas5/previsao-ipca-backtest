"""Backtest walk-forward, métricas, teste de Diebold-Mariano e intervalos conformais.

Módulos
-------
walk_forward
    ``run_walk_forward``: janela expansiva com guarda explícita contra vazamento.
metrics
    MAE/RMSE por horizonte (com IC por bootstrap em blocos), fatias e piores erros.
diebold_mariano
    ``diebold_mariano``: teste de igualdade de acurácia preditiva (correção HLN).
conformal
    ``add_conformal_intervals``: intervalos conformais calibrados só com erros já conhecidos.
"""
