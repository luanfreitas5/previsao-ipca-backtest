"""Leitura de dados do disco com mensagens de erro claras em pt-BR."""

import json
import logging
from pathlib import Path
from typing import Any

import polars as pl

from exceptions.data import DataValidationError

logger = logging.getLogger(__name__)


def read_parquet(path: Path) -> pl.DataFrame:
    """Lê um arquivo Parquet.

    Parameters
    ----------
    path : Path
        Arquivo de origem.

    Returns
    -------
    pl.DataFrame
        Dados lidos.

    Raises
    ------
    FileNotFoundError
        Se o arquivo não existir (ex.: etapa anterior do pipeline não rodou).

    Examples
    --------
    >>> read_parquet(Path("data/gold/ledger.parquet"))  # doctest: +SKIP
    """
    if not path.is_file():
        logger.error("Arquivo não encontrado: %s", path)
        raise FileNotFoundError(
            f"Arquivo não encontrado: {path}. Rode a etapa anterior do pipeline."
        )
    return pl.read_parquet(path)


def read_json(path: Path) -> Any:
    """Lê um arquivo JSON.

    Parameters
    ----------
    path : Path
        Arquivo de origem.

    Returns
    -------
    Any
        Conteúdo desserializado.

    Raises
    ------
    FileNotFoundError
        Se o arquivo não existir.
    DataValidationError
        Se o conteúdo não for um JSON válido.

    Examples
    --------
    >>> read_json(Path("manifest.json"))  # doctest: +SKIP
    """
    if not path.is_file():
        raise FileNotFoundError(f"Arquivo não encontrado: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise DataValidationError(f"JSON inválido em {path}") from error
