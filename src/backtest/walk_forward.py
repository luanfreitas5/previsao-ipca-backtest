"""Backtest walk-forward com janela expansiva e guarda contra vazamento temporal."""

import logging
import math
from collections.abc import Sequence
from datetime import date
from typing import Any, cast

import numpy as np
import polars as pl
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)

from config.logging import CONSOLE
from exceptions.data import LeakageError
from models.base import ForecastContext, Forecaster
from schemas.datasets import FORECASTS_SCHEMA, validate_dataframe

logger = logging.getLogger(__name__)

_MODEL_ERRORS = (ValueError, RuntimeError, ArithmeticError, np.linalg.LinAlgError)
_RESULT_SCHEMA = {
    "model": pl.String,
    "origin": pl.Date,
    "horizon": pl.Int64,
    "target_period": pl.Date,
    "target_available_at": pl.Date,
    "y_true": pl.Float64,
    "y_pred": pl.Float64,
}


def assert_no_leakage(context: ForecastContext) -> None:
    """Falha se o contexto contiver qualquer informação posterior à origem.

    Verifica (1) IPCA no histórico divulgado após a origem, (2) alvos de treino
    divulgados após a origem e (3) linhas de teste de outra origem.

    Parameters
    ----------
    context : ForecastContext
        Contexto a verificar.

    Raises
    ------
    LeakageError
        Se qualquer verificação falhar.

    Examples
    --------
    >>> assert_no_leakage(context)  # doctest: +SKIP
    """
    latest_history = cast("date | None", context.ipca_history["available_at"].max())
    if latest_history is not None and latest_history > context.origin:
        raise LeakageError(f"IPCA divulgado em {latest_history} usado na origem {context.origin}")
    latest_target = (
        cast("date | None", context.train["target_available_at"].max())
        if context.train.height
        else None
    )
    if latest_target is not None and latest_target > context.origin:
        raise LeakageError(f"Alvo de treino divulgado em {latest_target} > origem {context.origin}")
    if context.test.height and context.test["origin"].n_unique() != 1:
        raise LeakageError("Linhas de teste de mais de uma origem no mesmo contexto")


def build_context(
    origin: date, ledger_ipca: pl.DataFrame, supervised: pl.DataFrame, horizons: Sequence[int]
) -> tuple[ForecastContext, pl.DataFrame]:
    """Monta o contexto de uma origem e separa o gabarito (alvos reais) do que o modelo vê.

    Parameters
    ----------
    origin : date
        Data de origem.
    ledger_ipca : pl.DataFrame
        Linhas do ledger com ``series == "ipca"``.
    supervised : pl.DataFrame
        Tabela supervisionada completa.
    horizons : Sequence[int]
        Horizontes avaliados.

    Returns
    -------
    tuple[ForecastContext, pl.DataFrame]
        Contexto (sem ``y_true`` na parte de teste) e o gabarito da origem.

    Raises
    ------
    LeakageError
        Se o contexto montado contiver informação futura.

    Examples
    --------
    >>> context, truth = build_context(
    ...     date(2020, 1, 31), ipca, supervised, [1, 3]
    ... )  # doctest: +SKIP
    """
    test_full = supervised.filter(pl.col("origin") == origin)
    context = ForecastContext(
        origin=origin,
        horizons=tuple(horizons),
        ipca_history=ledger_ipca.filter(pl.col("available_at") <= origin).sort("period"),
        train=supervised.filter(pl.col("target_available_at") <= origin),
        test=test_full.drop("y_true", "target_available_at"),
    )
    assert_no_leakage(context)
    truth = test_full.select("horizon", "target_period", "target_available_at", "y_true")
    return context, truth


def run_walk_forward(
    supervised: pl.DataFrame,
    ledger: pl.DataFrame,
    models: Sequence[Forecaster],
    origins: Sequence[date],
    show_progress: bool = True,
) -> pl.DataFrame:
    """Executa o backtest com janela expansiva: a cada origem, reajusta e prevê.

    Parameters
    ----------
    supervised : pl.DataFrame
        Tabela supervisionada (``build_supervised_frame``).
    ledger : pl.DataFrame
        Ledger point-in-time.
    models : Sequence[Forecaster]
        Modelos a avaliar (incluindo o baseline Focus).
    origins : Sequence[date]
        Origens a avaliar, em ordem crescente.
    show_progress : bool, optional
        Exibe barra de progresso rich, by default ``True``.

    Returns
    -------
    pl.DataFrame
        Previsões em formato longo (``model``, ``origin``, ``horizon``, ``target_period``,
        ``target_available_at``, ``y_true``, ``y_pred``); ``y_pred`` é nulo quando o
        modelo falhou ou não tinha dados.

    Raises
    ------
    LeakageError
        Se algum contexto contiver informação futura.

    Examples
    --------
    >>> run_walk_forward(supervised, ledger, models, origins)  # doctest: +SKIP
    """
    horizons = sorted(supervised["horizon"].unique().to_list())
    ipca = ledger.filter(pl.col("series") == "ipca")
    rows: list[dict[str, Any]] = []
    progress = Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
        console=CONSOLE,
        disable=not show_progress,
    )
    with progress:
        task = progress.add_task("Backtest walk-forward", total=len(origins))
        for origin in origins:
            context, truth = build_context(origin, ipca, supervised, horizons)
            progress.advance(task)
            if truth.drop_nulls("y_true").is_empty():
                continue
            for model in models:
                rows.extend(_score_model(model, context, truth))
    result = pl.DataFrame(rows, schema=_RESULT_SCHEMA)
    logger.info("Backtest concluído: %d previsões, %d origens", result.height, len(origins))
    return validate_dataframe(result, FORECASTS_SCHEMA, "forecasts")


def _score_model(
    model: Forecaster, context: ForecastContext, truth: pl.DataFrame
) -> list[dict[str, Any]]:
    """Prevê com um modelo e emparelha cada previsão com o alvo realizado."""
    try:
        predictions = model.forecast(context)
    except _MODEL_ERRORS as error:
        logger.warning("Modelo %s falhou na origem %s: %s", model.name, context.origin, error)
        predictions = {}
    rows = []
    for item in truth.drop_nulls("y_true").iter_rows(named=True):
        value = predictions.get(item["horizon"], math.nan)
        rows.append(
            {
                "model": model.name,
                "origin": context.origin,
                "horizon": item["horizon"],
                "target_period": item["target_period"],
                "target_available_at": item["target_available_at"],
                "y_true": item["y_true"],
                "y_pred": None if value is None or math.isnan(value) else float(value),
            }
        )
    return rows
