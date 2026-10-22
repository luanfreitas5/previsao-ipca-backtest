"""Testes dos intervalos conformais (sem vazamento e com cobertura aproximada)."""

import math
from datetime import date, timedelta
from typing import cast

import numpy as np
import polars as pl
import pytest

from backtest.conformal import add_conformal_intervals, compute_coverage, conformal_quantile

pytestmark = pytest.mark.leakage


def make_series(n: int = 120, delay_days: int = 45, seed: int = 0) -> pl.DataFrame:
    rng = np.random.default_rng(seed)
    origins = [date(2010, 1, 1) + timedelta(days=30 * i) for i in range(n)]
    truth = rng.normal(0.5, 0.3, n)
    return pl.DataFrame(
        {
            "model": ["m"] * n,
            "origin": origins,
            "horizon": [1] * n,
            "target_period": origins,
            "target_available_at": [o + timedelta(days=delay_days) for o in origins],
            "y_true": truth,
            "y_pred": truth + rng.normal(0, 0.2, n),
        }
    )


def test_conformal_quantile_picks_expected_rank():
    assert conformal_quantile(np.arange(1.0, 11.0), 0.2) == 9.0


def test_conformal_quantile_needs_enough_scores():
    assert math.isnan(conformal_quantile(np.array([1.0, 2.0]), 0.05))
    assert math.isnan(conformal_quantile(np.array([]), 0.1))


def test_intervals_absent_until_minimum_calibration():
    out = add_conformal_intervals(make_series(), alpha=0.1, min_calibration=30)
    assert out["lower"].head(30).null_count() == 30
    assert out["lower"].tail(5).null_count() == 0


def test_intervals_are_centered_on_forecast():
    out = add_conformal_intervals(make_series(), alpha=0.1, min_calibration=20).drop_nulls("lower")
    asymmetry = ((out["upper"] - out["y_pred"]) - (out["y_pred"] - out["lower"])).abs().max()
    assert cast("float", asymmetry) < 1e-9
    assert (out["upper"] >= out["lower"]).all()


def test_interval_ignores_targets_not_yet_published():
    """Mudar alvos ainda não divulgados na origem i não altera o intervalo da linha i."""
    series = make_series()
    row = 100
    base = add_conformal_intervals(series, 0.1, 20).row(row, named=True)
    tampered_truth = (
        pl.when(pl.int_range(pl.len()) > row - 2)
        .then(pl.col("y_true") + 50)
        .otherwise(pl.col("y_true"))
    )
    # linhas row-1 e row têm alvo divulgado depois da origem da linha `row` (45 dias > 30 dias)
    changed = add_conformal_intervals(
        series.with_columns(tampered_truth.alias("y_true")), 0.1, 20
    ).row(row, named=True)
    assert (changed["lower"], changed["upper"]) == (base["lower"], base["upper"])


def test_coverage_is_close_to_nominal_for_stationary_errors():
    series = make_series(n=600, delay_days=1, seed=3)
    coverage = compute_coverage(add_conformal_intervals(series, alpha=0.1, min_calibration=40))
    assert 0.84 <= coverage["coverage"][0] <= 0.96
    assert coverage["mean_width"][0] > 0
