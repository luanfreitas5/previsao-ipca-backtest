"""Estágios do pipeline: bronze -> silver -> gold -> backtest -> relatório."""

import logging
from datetime import date
from pathlib import Path
from typing import cast

import polars as pl

from backtest.walk_forward import run_walk_forward
from config.settings import Settings
from data.bcb_client import BcbClient
from data.cleaning import clean_focus, clean_sgs
from data.downloader import find_latest_snapshot, ingest_all, load_snapshot_records
from data.reader import read_parquet
from data.writer import write_parquet
from exceptions.base import ConfigurationError
from experiment.tracker import log_backtest_run
from features.dataset import build_supervised_frame
from features.ledger import build_ledger
from features.point_in_time import get_feature_columns
from models.factory import build_models
from reporting.analysis import Analysis, analyze_forecasts
from reporting.report import render_report, write_report
from schemas.datasets import SGS_SILVER_SCHEMA, validate_dataframe
from utils.dates import generate_month_ends, month_end
from utils.hashing import hash_file
from visualization.plots import (
    plot_conformal_coverage,
    plot_forecasts_vs_actual,
    plot_rmse_by_horizon,
)
from visualization.theme import save_figure

logger = logging.getLogger(__name__)

SILVER_SGS = "sgs.parquet"
SILVER_FOCUS = "focus.parquet"
GOLD_LEDGER = "ledger.parquet"
GOLD_SUPERVISED = "supervised.parquet"
GOLD_FORECASTS = "forecasts.parquet"


def run_ingest(settings: Settings, force: bool = False) -> None:
    """Estágio 1: baixa SGS e Focus para a bronze (idempotente, com cache do dia).

    Parameters
    ----------
    settings : Settings
        Configuração validada.
    force : bool, optional
        Refaz o snapshot do dia, by default ``False``.

    Examples
    --------
    >>> run_ingest(settings)  # doctest: +SKIP
    """
    ingest_all(settings, BcbClient(settings.data), date.today(), force)


def run_silver(settings: Settings) -> None:
    """Estágio 2: bronze -> silver (tipagem, deduplicação, validação).

    Parameters
    ----------
    settings : Settings
        Configuração validada.

    Examples
    --------
    >>> run_silver(settings)  # doctest: +SKIP
    """
    bronze, silver = settings.paths.data_bronze, settings.paths.data_silver
    frames = []
    for name in settings.series_names:
        snapshot = find_latest_snapshot(bronze, f"sgs_{name}")
        frames.append(clean_sgs(load_snapshot_records(snapshot), name))
    sgs = validate_dataframe(pl.concat(frames), SGS_SILVER_SCHEMA, "sgs_silver")
    write_parquet(sgs, silver / SILVER_SGS)
    focus_snapshot = find_latest_snapshot(bronze, "focus")
    write_parquet(clean_focus(load_snapshot_records(focus_snapshot)), silver / SILVER_FOCUS)


def run_gold(settings: Settings) -> None:
    """Estágio 3: silver -> gold (ledger point-in-time e tabela supervisionada).

    Parameters
    ----------
    settings : Settings
        Configuração validada.

    Raises
    ------
    ConfigurationError
        Se a série ``ipca`` não estiver no catálogo.

    Examples
    --------
    >>> run_gold(settings)  # doctest: +SKIP
    """
    if "ipca" not in settings.series_names:
        raise ConfigurationError("O catálogo de séries deve conter 'ipca' (variável-alvo)")
    silver, gold = settings.paths.data_silver, settings.paths.data_gold
    ledger = build_ledger(read_parquet(silver / SILVER_SGS), settings.series)
    last_period = cast("date", ledger.filter(pl.col("series") == "ipca")["period"].max())
    cfg = settings.backtest
    last_origin = cfg.last_origin or month_end(last_period)
    first_origin = month_end(settings.data.start_date)
    supervised = build_supervised_frame(
        ledger,
        read_parquet(silver / SILVER_FOCUS),
        generate_month_ends(first_origin, last_origin),
        cfg.horizons,
        settings.series_names,
        cfg.n_lags,
        settings.focus.publication_lag_days,
        settings.focus.max_staleness_days,
    )
    write_parquet(ledger, gold / GOLD_LEDGER)
    write_parquet(supervised, gold / GOLD_SUPERVISED)


def run_backtest(settings: Settings) -> None:
    """Estágio 4: backtest walk-forward, intervalos conformais e registro no MLflow.

    Parameters
    ----------
    settings : Settings
        Configuração validada.

    Examples
    --------
    >>> run_backtest(settings)  # doctest: +SKIP
    """
    gold = settings.paths.data_gold
    ledger = read_parquet(gold / GOLD_LEDGER)
    supervised = read_parquet(gold / GOLD_SUPERVISED)
    columns = get_feature_columns(settings.series_names, settings.backtest.n_lags)
    origins = [
        o
        for o in sorted(supervised["origin"].unique().to_list())
        if o >= settings.backtest.first_origin
    ]
    forecasts = run_walk_forward(supervised, ledger, build_models(settings, columns), origins)
    write_parquet(forecasts, gold / GOLD_FORECASTS)
    analysis = analyze_forecasts(forecasts, settings)
    tables = _write_tables(analysis, settings.paths.tables)
    hashes = {
        "ledger": hash_file(gold / GOLD_LEDGER),
        "supervised": hash_file(gold / GOLD_SUPERVISED),
        "focus": hash_file(settings.paths.data_silver / SILVER_FOCUS),
    }
    log_backtest_run(settings, analysis.metrics, hashes, [*tables, gold / GOLD_FORECASTS])


def run_report(settings: Settings) -> Path:
    """Estágio 5: tabelas, figuras (PNG 300 dpi + SVG) e ``reports/relatorio_final.md``.

    Parameters
    ----------
    settings : Settings
        Configuração validada.

    Returns
    -------
    Path
        Caminho do relatório gerado.

    Examples
    --------
    >>> run_report(settings)  # doctest: +SKIP
    """
    forecasts = read_parquet(settings.paths.data_gold / GOLD_FORECASTS)
    analysis = analyze_forecasts(forecasts, settings)
    _write_tables(analysis, settings.paths.tables)
    figures = _write_figures(analysis, settings)
    text = render_report(analysis, settings, figures)
    return write_report(text, settings.paths.reports / "relatorio_final.md")


def _write_tables(analysis: Analysis, directory: Path) -> list[Path]:
    """Grava as tabelas de resultados em CSV."""
    directory.mkdir(parents=True, exist_ok=True)
    tables = {
        "metricas_por_horizonte": analysis.metrics,
        "diebold_mariano_quadratica": analysis.dm_squared,
        "diebold_mariano_absoluta": analysis.dm_absolute,
        "metricas_por_periodo": analysis.slices,
        "cobertura_conformal": analysis.coverage,
        "piores_erros": analysis.worst,
    }
    paths = []
    for name, table in tables.items():
        path = directory / f"{name}.csv"
        table.write_csv(path)
        paths.append(path)
    return paths


def _write_figures(analysis: Analysis, settings: Settings) -> list[str]:
    """Gera e salva as figuras do relatório; devolve os nomes-base."""
    reference = settings.report.reference_model
    horizons = settings.backtest.horizons
    compared = [reference, analysis.best_model]
    figures = {
        "rmse_por_horizonte": plot_rmse_by_horizon(analysis.metrics),
        f"previsto_vs_realizado_h{horizons[0]}": plot_forecasts_vs_actual(
            analysis.forecasts, horizons[0], compared
        ),
        f"previsto_vs_realizado_h{horizons[-1]}": plot_forecasts_vs_actual(
            analysis.forecasts, horizons[-1], compared
        ),
        "cobertura_conformal": plot_conformal_coverage(
            analysis.coverage, 1 - settings.backtest.alpha
        ),
    }
    for name, figure in figures.items():
        save_figure(figure, settings.paths.figures, name)
    return list(figures)
