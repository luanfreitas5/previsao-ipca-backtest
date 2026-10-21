"""Ledger point-in-time: cada observação mensal carrega a data em que se tornou pública."""

import logging

import polars as pl

from config.settings import SeriesConfig
from schemas.datasets import validate_ledger

logger = logging.getLogger(__name__)

# Tolerância (dias) entre o último dado diário e o fim do mês para considerar o mês completo.
MONTH_COMPLETENESS_DAYS = 5


def aggregate_to_monthly(sgs: pl.DataFrame, config: SeriesConfig) -> pl.DataFrame:
    """Agrega uma série SGS para frequência mensal (``period`` = primeiro dia do mês).

    Séries diárias usam ``config.aggregation``. Meses incompletos (último dado a mais
    de ``MONTH_COMPLETENESS_DAYS`` dias do fim do mês) são descartados: um mês parcial
    tem valor diferente do definitivo e criaria divergência entre treino e uso real.

    Parameters
    ----------
    sgs : pl.DataFrame
        Colunas ``date`` e ``value`` de uma única série.
    config : SeriesConfig
        Regra de agregação e frequência.

    Returns
    -------
    pl.DataFrame
        Colunas ``period`` e ``value`` ordenadas.

    Examples
    --------
    >>> aggregate_to_monthly(daily_df, fx_config)  # doctest: +SKIP
    """
    monthly = sgs.with_columns(pl.col("date").dt.truncate("1mo").alias("period"))
    if config.frequency == "monthly":
        return monthly.select("period", "value").sort("period")
    agg = {
        "last": pl.col("value").last(),
        "mean": pl.col("value").mean(),
        "sum": pl.col("value").sum(),
    }
    grouped = (
        monthly.sort("date")
        .group_by("period")
        .agg(agg[config.aggregation].alias("value"), pl.col("date").max().alias("last_date"))
        .sort("period")
    )
    complete = pl.col("last_date") >= pl.col("period").dt.month_end().dt.offset_by(
        f"-{MONTH_COMPLETENESS_DAYS}d"
    )
    return grouped.filter(complete).select("period", "value")


def apply_transform(monthly: pl.DataFrame, transform: str) -> pl.DataFrame:
    """Aplica a transformação mensal; usa só o mês corrente e o anterior.

    Parameters
    ----------
    monthly : pl.DataFrame
        Colunas ``period`` e ``value`` ordenadas e contíguas.
    transform : str
        ``"level"``, ``"pct_change"`` (em %) ou ``"diff"``.

    Returns
    -------
    pl.DataFrame
        Mesmas colunas, sem a primeira linha quando a transformação cria nulo.

    Raises
    ------
    ValueError
        Se a transformação for desconhecida.

    Examples
    --------
    >>> apply_transform(monthly_df, "pct_change")  # doctest: +SKIP
    """
    value = pl.col("value")
    if transform == "level":
        return monthly
    if transform == "pct_change":
        expr = (value / value.shift(1) - 1) * 100
    elif transform == "diff":
        expr = value - value.shift(1)
    else:
        raise ValueError(f"Transformação desconhecida: {transform}")
    return monthly.sort("period").with_columns(expr.alias("value")).drop_nulls("value")


def add_availability(monthly: pl.DataFrame, release_lag_days: int) -> pl.DataFrame:
    """Adiciona ``available_at`` = fim do mês de referência + atraso de divulgação.

    Parameters
    ----------
    monthly : pl.DataFrame
        Coluna ``period``.
    release_lag_days : int
        Dias entre o fim do mês e a divulgação.

    Returns
    -------
    pl.DataFrame
        DataFrame com a coluna ``available_at`` (``Date``).

    Examples
    --------
    >>> add_availability(monthly_df, 10)  # doctest: +SKIP
    """
    return monthly.with_columns(
        pl.col("period").dt.month_end().dt.offset_by(f"{release_lag_days}d").alias("available_at")
    )


def build_ledger(sgs: pl.DataFrame, configs: list[SeriesConfig]) -> pl.DataFrame:
    """Constrói o ledger point-in-time de todas as séries.

    Parameters
    ----------
    sgs : pl.DataFrame
        Silver em formato longo (``series``, ``date``, ``value``).
    configs : list[SeriesConfig]
        Catálogo de séries com agregação, transformação e atraso.

    Returns
    -------
    pl.DataFrame
        Colunas ``series``, ``period``, ``value``, ``available_at``, validadas.

    Raises
    ------
    DataValidationError
        Se o ledger violar o contrato (ex.: meses faltantes).

    Examples
    --------
    >>> build_ledger(sgs_silver, settings.series)  # doctest: +SKIP
    """
    parts = []
    for config in configs:
        raw = sgs.filter(pl.col("series") == config.name)
        monthly = apply_transform(aggregate_to_monthly(raw, config), config.transform)
        parts.append(
            add_availability(monthly, config.release_lag_days).select(
                pl.lit(config.name).alias("series"), "period", "value", "available_at"
            )
        )
    ledger = pl.concat(parts).sort("series", "period")
    logger.info("Ledger construído: %d observações", ledger.height)
    return validate_ledger(ledger)
