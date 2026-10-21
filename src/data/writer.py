"""Escrita de dados em disco (Parquet e JSON), criando diretórios quando necessário."""

import json
import logging
from pathlib import Path
from typing import Any

import polars as pl

logger = logging.getLogger(__name__)


def write_parquet(df: pl.DataFrame, path: Path) -> Path:
    """Grava um DataFrame em Parquet (compressão zstd).

    Parameters
    ----------
    df : pl.DataFrame
        Dados a gravar.
    path : Path
        Arquivo de destino (diretórios pai são criados).

    Returns
    -------
    Path
        O caminho gravado.

    Examples
    --------
    >>> write_parquet(df, Path("data/gold/ledger.parquet"))  # doctest: +SKIP
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(path, compression="zstd")
    logger.info("Gravado %s (%d linhas)", path, df.height)
    return path


def write_json_atomic(payload: Any, path: Path) -> Path:
    """Grava JSON de forma atômica (arquivo temporário + ``Path.replace``).

    Evita deixar arquivo pela metade se o processo for interrompido.

    Parameters
    ----------
    payload : Any
        Objeto serializável em JSON.
    path : Path
        Arquivo de destino (diretórios pai são criados).

    Returns
    -------
    Path
        O caminho gravado.

    Examples
    --------
    >>> write_json_atomic({"a": 1}, Path("manifest.json"))  # doctest: +SKIP
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)
    return path
