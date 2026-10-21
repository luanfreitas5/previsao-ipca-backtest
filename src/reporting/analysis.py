"""Consolida todas as análises sobre as previsões do backtest."""

from dataclasses import dataclass

import polars as pl

from backtest.conformal import add_conformal_intervals, compute_coverage
from backtest.diebold_mariano import run_dm_against_reference
from backtest.metrics import (
    add_relative_rmse,
    compute_metrics,
    compute_metrics_by_slice,
    find_worst_errors,
    prepare_errors,
    restrict_to_common_sample,
)
from config.settings import Settings


@dataclass(frozen=True)
class Analysis:
    """Resultados prontos para o relatório.

    Attributes
    ----------
    forecasts : pl.DataFrame
        Previsões com intervalos conformais (``lower``/``upper``).
    metrics : pl.DataFrame
        MAE/RMSE/viés por modelo e horizonte (amostra comum) com IC e ``rmse_ratio``.
    dm_squared, dm_absolute : pl.DataFrame
        Diebold-Mariano contra a referência com perda quadrática e absoluta.
    slices : pl.DataFrame
        Métricas por subperíodo.
    coverage : pl.DataFrame
        Cobertura e largura dos intervalos conformais.
    worst : pl.DataFrame
        Maiores erros absolutos do melhor modelo (RMSE médio) que não é a referência.
    best_model : str
        Modelo (exceto a referência) com menor RMSE médio entre horizontes.
    """

    forecasts: pl.DataFrame
    metrics: pl.DataFrame
    dm_squared: pl.DataFrame
    dm_absolute: pl.DataFrame
    slices: pl.DataFrame
    coverage: pl.DataFrame
    worst: pl.DataFrame
    best_model: str


def analyze_forecasts(forecasts: pl.DataFrame, settings: Settings) -> Analysis:
    """Executa todas as análises do relatório sobre as previsões do backtest.

    Métricas, testes e fatias usam a AMOSTRA COMUM (origens/horizontes em que todos os
    modelos e o Focus têm previsão), para que a comparação seja justa.

    Parameters
    ----------
    forecasts : pl.DataFrame
        Saída de ``run_walk_forward``.
    settings : Settings
        Configuração validada.

    Returns
    -------
    Analysis
        Tabelas e métricas consolidadas.

    Examples
    --------
    >>> analysis = analyze_forecasts(forecasts, settings)  # doctest: +SKIP
    """
    reference = settings.report.reference_model
    errors = restrict_to_common_sample(prepare_errors(forecasts))
    metrics = add_relative_rmse(
        compute_metrics(errors, n_bootstrap=settings.report.n_bootstrap, seed=settings.random_seed),
        reference,
    )
    intervals = add_conformal_intervals(
        forecasts, settings.backtest.alpha, settings.backtest.min_calibration
    )
    best_model = (
        metrics.filter(pl.col("model") != reference)
        .group_by("model")
        .agg(pl.col("rmse").mean())
        .sort("rmse")["model"][0]
    )
    slices = [(s.name, s.start, s.end) for s in settings.report.slices]
    return Analysis(
        forecasts=intervals,
        metrics=metrics,
        dm_squared=run_dm_against_reference(errors, reference, "squared"),
        dm_absolute=run_dm_against_reference(errors, reference, "absolute"),
        slices=compute_metrics_by_slice(errors, slices),
        coverage=compute_coverage(intervals),
        worst=find_worst_errors(errors, best_model, settings.report.worst_errors_k),
        best_model=best_model,
    )
