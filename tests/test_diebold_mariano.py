"""Testes do teste de Diebold-Mariano (HLN)."""

import math

import numpy as np
import polars as pl
import pytest

from backtest.diebold_mariano import diebold_mariano, run_dm_against_reference
from backtest.metrics import prepare_errors
from helpers import make_forecasts


@pytest.mark.smoke
def test_more_accurate_model_has_negative_statistic_and_small_p():
    rng = np.random.default_rng(0)
    good, bad = rng.normal(0, 0.5, 200), rng.normal(0, 2.0, 200)
    result = diebold_mariano(good, bad, horizon=1, alternative="less")
    assert result.statistic < 0
    assert result.p_value < 0.001
    assert result.mean_diff < 0


def test_swapping_models_flips_the_sign():
    rng = np.random.default_rng(1)
    a, b = rng.normal(0, 1, 80), rng.normal(0, 1.5, 80)
    forward, backward = diebold_mariano(a, b, 3), diebold_mariano(b, a, 3)
    assert forward.statistic == pytest.approx(-backward.statistic)
    assert forward.p_value == pytest.approx(backward.p_value)


def test_matches_manual_computation_for_horizon_one():
    rng = np.random.default_rng(2)
    a, b = rng.normal(0, 1, 50), rng.normal(0, 1.2, 50)
    d = a**2 - b**2
    n = len(d)
    manual = math.sqrt((n - 1) / n) * d.mean() / math.sqrt(d.var() / n)  # HLN com h = 1
    assert diebold_mariano(a, b, 1).statistic == pytest.approx(manual)


def test_identical_errors_yield_nan():
    errors = np.random.default_rng(3).normal(size=30)
    result = diebold_mariano(errors, errors)
    assert math.isnan(result.statistic)
    assert math.isnan(result.p_value)


def test_too_short_sample_yields_nan():
    result = diebold_mariano(np.array([1.0, 2.0, 3.0]), np.array([1.5, 1.0, 2.0]), horizon=2)
    assert math.isnan(result.statistic)
    assert result.n == 3


def test_one_sided_p_values_are_complementary():
    rng = np.random.default_rng(4)
    a, b = rng.normal(0, 1, 60), rng.normal(0, 1.3, 60)
    less = diebold_mariano(a, b, alternative="less").p_value
    greater = diebold_mariano(a, b, alternative="greater").p_value
    assert less + greater == pytest.approx(1.0)


def test_invalid_arguments_raise():
    with pytest.raises(ValueError):
        diebold_mariano(np.zeros(3), np.zeros(4))
    with pytest.raises(ValueError):
        diebold_mariano(np.zeros(5), np.zeros(5), horizon=0)


def test_absolute_loss_is_supported():
    rng = np.random.default_rng(5)
    result = diebold_mariano(rng.normal(0, 0.5, 100), rng.normal(0, 2, 100), loss="absolute")
    assert result.statistic < 0


def test_run_against_reference_covers_every_model_and_horizon():
    errors = prepare_errors(make_forecasts(("arima", "ets", "focus"), (1, 3)))
    table = run_dm_against_reference(errors, "focus")
    assert table.height == 4
    assert set(table["model"]) == {"arima", "ets"}
    assert table.filter(pl.col("n") > 0).height == 4
