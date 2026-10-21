"""Limpeza bronze -> silver: tipagem, deduplicação e validação por contrato."""

import logging
from typing import Any

import polars as pl

from exceptions.data import DataValidationError
from schemas.datasets import (
    FOCUS_SILVER_SCHEMA,
    SGS_SILVER_SCHEMA,
    validate_dataframe,
)

logger = logging.getLogger(__name__)


def clean_sgs(records: list[dict[str, Any]], series_name: str) -> pl.DataFrame:
    """Converte os registros brutos do SGS em um DataFrame tipado e validado.

    Datas ``dd/MM/yyyy`` viram ``Date``; ``valor`` (texto) vira ``Float64``; linhas
    com data ou valor inválidos são descartadas; duplicatas por data mantêm a última.

    Parameters
    ----------
    records : list[dict[str, Any]]
        Registros ``{"data", "valor"}`` da bronze.
    series_name : str
        Nome da série (vira a coluna ``series``).

    Returns
    -------
    pl.DataFrame
        Colunas ``series``, ``date``, ``value`` ordenadas por data.

    Raises
    ------
    DataValidationError
        Se não restar nenhuma linha válida ou o contrato for violado.

    Examples
    --------
    >>> clean_sgs([{"data": "01/01/2020", "valor": "0.21"}], "ipca").shape
    (1, 3)
    """
    if not records:
        raise DataValidationError(f"Série '{series_name}' sem registros na bronze")
    df = (
        pl.from_dicts(records, infer_schema_length=None)
        .select(
            pl.lit(series_name).alias("series"),
            pl.col("data").cast(pl.String).str.to_date("%d/%m/%Y", strict=False).alias("date"),
            pl.col("valor").cast(pl.String).cast(pl.Float64, strict=False).alias("value"),
        )
        .drop_nulls(["date", "value"])
        .unique(subset=["series", "date"], keep="last", maintain_order=True)
        .sort("date")
    )
    if df.is_empty():
        raise DataValidationError(f"Série '{series_name}' sem linhas válidas após a limpeza")
    return validate_dataframe(df, SGS_SILVER_SCHEMA, f"sgs_{series_name}")


def clean_focus(records: list[dict[str, Any]]) -> pl.DataFrame:
    """Converte as expectativas brutas do Focus em um DataFrame tipado e validado.

    ``DataReferencia`` (``MM/AAAA``) vira o primeiro dia do mês de referência.

    Parameters
    ----------
    records : list[dict[str, Any]]
        Registros do Olinda (``Data``, ``DataReferencia``, ``Mediana`` ...).

    Returns
    -------
    pl.DataFrame
        Colunas ``survey_date``, ``reference_month``, ``median``, ``mean``, ``std``,
        ``min``, ``max``, ``n_respondents``.

    Raises
    ------
    DataValidationError
        Se não restar nenhuma linha válida ou o contrato for violado.

    Examples
    --------
    >>> clean_focus([{"Data": "2020-01-06", "DataReferencia": "02/2020", "Mediana": 0.2}]).shape
    (1, 8)
    """
    if not records:
        raise DataValidationError("Focus sem registros na bronze")
    raw = pl.from_dicts(records, infer_schema_length=None)
    optional = ["Media", "DesvioPadrao", "Minimo", "Maximo", "numeroRespondentes"]
    df = (
        raw.with_columns(
            [pl.lit(None, dtype=pl.Float64).alias(c) for c in optional if c not in raw.columns]
        )
        .select(
            pl.col("Data")
            .cast(pl.String)
            .str.to_date("%Y-%m-%d", strict=False)
            .alias("survey_date"),
            (pl.lit("01/") + pl.col("DataReferencia").cast(pl.String))
            .str.to_date("%d/%m/%Y", strict=False)
            .alias("reference_month"),
            pl.col("Mediana").cast(pl.Float64, strict=False).alias("median"),
            pl.col("Media").cast(pl.Float64, strict=False).alias("mean"),
            pl.col("DesvioPadrao").cast(pl.Float64, strict=False).alias("std"),
            pl.col("Minimo").cast(pl.Float64, strict=False).alias("min"),
            pl.col("Maximo").cast(pl.Float64, strict=False).alias("max"),
            pl.col("numeroRespondentes").cast(pl.Int64, strict=False).alias("n_respondents"),
        )
        .drop_nulls(["survey_date", "reference_month", "median"])
        .unique(subset=["survey_date", "reference_month"], keep="last", maintain_order=True)
        .sort("survey_date", "reference_month")
    )
    if df.is_empty():
        raise DataValidationError("Focus sem linhas válidas após a limpeza")
    return validate_dataframe(df, FOCUS_SILVER_SCHEMA, "focus")
