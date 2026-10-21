"""Construção point-in-time do ledger e das features (sem informação futura).

Módulos
-------
ledger
    Agrega as séries para frequência mensal e atribui ``available_at`` (data de divulgação).
point_in_time
    Matriz de lags de cada série vista a partir de cada data de origem.
dataset
    Tabela supervisionada (origem x horizonte) com alvo, features e Focus.
"""
