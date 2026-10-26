"""Rastreamento de experimentos com MLflow.

Módulos
-------
tracker
    ``log_backtest_run``: registra parâmetros, métricas, artefatos e as tags de linhagem
    (``git_sha``, ``git_dirty``, ``data_hash``, ``seed``) no run pai e nos runs filhos.
"""
