"""Ingestão, persistência e limpeza de dados.

Módulos
-------
bcb_client
    ``BcbClient``: cliente HTTP das APIs SGS e Olinda (Focus) com retry e janelas.
downloader
    Ingestão idempotente para ``data/bronze`` (snapshots datados + manifesto).
cleaning
    Conversão bronze -> silver (tipagem, deduplicação, validação).
reader, writer
    Leitura e escrita de Parquet/JSON com mensagens de erro claras.
"""
