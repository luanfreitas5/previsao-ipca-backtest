"""Tabela supervisionada: uma linha por (origem, horizonte) com alvo, features e Focus."""

from collections.abc import Sequence
from datetime import date

import polars as pl

from features.point_in_time import add_derived_features, build_feature_frame


def attach_focus(
    frame: pl.DataFrame,
    focus: pl.DataFrame,
    publication_lag_days: int,
    max_staleness_days: int,
) -> pl.DataFrame:
    """Anexa a mediana do Focus vigente na origem para o mês-alvo (point-in-time).

    O Focus também respeita a disponibilidade: um snapshot de data ``d`` só é
    público a partir de ``d + publication_lag_days``. Snapshots mais velhos que
    ``max_staleness_days`` na origem são descartados (``focus_median`` nulo).

    Parameters
    ----------
    frame : pl.DataFrame
        Colunas ``origin`` e ``target_period``.
    focus : pl.DataFrame
        Silver do Focus (``survey_date``, ``reference_month``, ``median``).
    publication_lag_days : int
        Atraso entre a data do snapshot e sua divulgação.
    max_staleness_days : int
        Idade máxima aceita do snapshot na origem.

    Returns
    -------
    pl.DataFrame
        ``frame`` com a coluna ``focus_median``.

    Examples
    --------
    >>> attach_focus(frame, focus, 3, 10)  # doctest: +SKIP
    """
    right = focus.select(
        pl.col("survey_date"),
        pl.col("survey_date").dt.offset_by(f"{publication_lag_days}d").alias("focus_available_at"),
        pl.col("reference_month").alias("target_period"),
        pl.col("median").alias("focus_median"),
    ).sort("focus_available_at")
    joined = frame.sort("origin").join_asof(
        right,
        left_on="origin",
        right_on="focus_available_at",
        by="target_period",
        strategy="backward",
    )
    stale = (pl.col("origin") - pl.col("survey_date")).dt.total_days() > max_staleness_days
    return joined.with_columns(
        pl.when(stale).then(None).otherwise(pl.col("focus_median")).alias("focus_median")
    ).drop("survey_date", "focus_available_at")


def build_supervised_frame(
    ledger: pl.DataFrame,
    focus: pl.DataFrame,
    origins: Sequence[date],
    horizons: Sequence[int],
    series_names: Sequence[str],
    n_lags: int,
    publication_lag_days: int,
    max_staleness_days: int,
) -> pl.DataFrame:
    """Constrói a tabela supervisionada usada pelo backtest.

    Para cada origem ``o`` (fim do mês ``t``) e horizonte ``h``, o alvo é o IPCA do
    mês ``t + h``. ``target_available_at`` registra quando esse alvo é divulgado:
    o backtest só pode usá-lo para treino depois dessa data.

    Parameters
    ----------
    ledger : pl.DataFrame
        Ledger point-in-time.
    focus : pl.DataFrame
        Silver do Focus.
    origins : Sequence[date]
        Datas de origem (fins de mês).
    horizons : Sequence[int]
        Horizontes em meses à frente do mês da origem.
    series_names : Sequence[str]
        Séries usadas como features.
    n_lags : int
        Número de lags por série (>= 12).
    publication_lag_days, max_staleness_days : int
        Regras de disponibilidade do Focus.

    Returns
    -------
    pl.DataFrame
        Colunas: ``origin``, ``horizon``, ``target_period``, ``y_true``,
        ``target_available_at``, ``steps_ahead``, ``target_month``, features e
        ``focus_median``. ``y_true`` é nulo se o alvo ainda não foi divulgado.

    Examples
    --------
    >>> build_supervised_frame(
    ...     ledger, focus, origins, [1, 3], ["ipca"], 12, 3, 10
    ... )  # doctest: +SKIP
    """
    features = add_derived_features(build_feature_frame(ledger, origins, series_names, n_lags))
    parts = [
        features.with_columns(
            pl.lit(h, dtype=pl.Int64).alias("horizon"),
            pl.col("origin").dt.truncate("1mo").dt.offset_by(f"{h}mo").alias("target_period"),
        )
        for h in horizons
    ]
    target = ledger.filter(pl.col("series") == "ipca").select(
        pl.col("period").alias("target_period"),
        pl.col("value").alias("y_true"),
        pl.col("available_at").alias("target_available_at"),
    )
    steps = (pl.col("target_period").dt.year() - pl.col("ipca_last_period").dt.year()) * 12 + (
        pl.col("target_period").dt.month() - pl.col("ipca_last_period").dt.month()
    )
    frame = (
        pl.concat(parts)
        .filter(pl.col("ipca_last_period").is_not_null())
        .join(target, on="target_period", how="left")
        .with_columns(
            steps.cast(pl.Int64).alias("steps_ahead"),
            pl.col("target_period").dt.month().cast(pl.Int64).alias("target_month"),
        )
    )
    return attach_focus(frame, focus, publication_lag_days, max_staleness_days).sort(
        "origin", "horizon"
    )
