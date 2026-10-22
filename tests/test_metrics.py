"""Testes das métricas de erro, bootstrap em blocos, fatias e piores erros."""

from datetime import date

import numpy as np
import polars as pl
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from backtest.metrics import (
    add_relative_rmse,
    block_bootstrap_means,
    compute_metrics,
    compute_metrics_by_slice,
    find_worst_errors,
    prepare_errors,
    restrict_to_common_sample,
)
from helpers import make_forecasts


def constant_error_frame(error: float, n: int = 40) -> pl.DataFrame:
    base = make_forecasts(("m",), (1,), n_origins=n)
    return base.with_columns((pl.col("y_true") + error).alias("y_pred"))


def test_prepare_errors_drops_missing_and_signs_error():
    frame = constant_error_frame(0.5).with_columns(
        pl.when(pl.col("origin") == pl.col("origin").min())
        .then(None)
        .otherwise(pl.col("y_pred"))
        .alias("y_pred")
    )
    errors = prepare_errors(frame)
    assert errors.height == frame.height - 1
    assert errors["error"].to_list() == pytest.approx([0.5] * errors.height)
    assert errors["sq_error"][0] == pytest.approx(0.25)


def test_metrics_for_constant_error():
    metrics = compute_metrics(prepare_errors(constant_error_frame(0.5)), n_bootstrap=200)
    row = metrics.row(0, named=True)
    assert row["mae"] == pytest.approx(0.5)
    assert row["rmse"] == pytest.approx(0.5)
    assert row["bias"] == pytest.approx(0.5)
    assert row["rmse_lo"] == pytest.approx(0.5)
    assert row["rmse_hi"] == pytest.approx(0.5)


def test_metrics_are_reproducible_given_seed():
    errors = prepare_errors(make_forecasts(("a", "b"), (1, 3)))
    first = compute_metrics(errors, n_bootstrap=200, seed=1)
    second = compute_metrics(errors, n_bootstrap=200, seed=1)
    assert first.equals(second)


def test_confidence_interval_is_ordered_and_near_point_estimate():
    metrics = compute_metrics(prepare_errors(make_forecasts(("a",), (1, 3))), n_bootstrap=500)
    assert (metrics["rmse_lo"] <= metrics["rmse_hi"]).all()
    assert (metrics["mae_lo"] <= metrics["mae_hi"]).all()
    # com 96 pontos o ponto fica dentro de uma faixa folgada em torno do IC
    assert (
        (metrics["rmse"] > metrics["rmse_lo"] * 0.8) & (metrics["rmse"] < metrics["rmse_hi"] * 1.2)
    ).all()


@given(n=st.integers(5, 60), block=st.integers(1, 12), n_boot=st.integers(5, 50))
@settings(max_examples=30, deadline=None)
def test_block_bootstrap_means_stay_within_data_range(n, block, n_boot):
    values = np.random.default_rng(0).normal(size=n)
    means = block_bootstrap_means(values, block, n_boot, np.random.default_rng(1))
    assert means.shape == (n_boot,)
    assert values.min() - 1e-9 <= means.min() and means.max() <= values.max() + 1e-9


def test_common_sample_keeps_only_origins_with_all_models():
    frame = make_forecasts(("a", "focus"), (1,), n_origins=10)
    frame = frame.filter(
        ~((pl.col("model") == "focus") & (pl.col("origin") == pl.col("origin").min()))
    )
    common = restrict_to_common_sample(prepare_errors(frame))
    assert common.height == 18
    assert common.group_by("origin").len()["len"].unique().to_list() == [2]


def test_relative_rmse_of_reference_is_one():
    errors = prepare_errors(make_forecasts(("arima", "focus"), (1, 3)))
    metrics = add_relative_rmse(compute_metrics(errors, n_bootstrap=100), "focus")
    focus = metrics.filter(pl.col("model") == "focus")
    assert focus["rmse_ratio"].to_list() == pytest.approx([1.0, 1.0])


def test_slices_group_by_target_month():
    errors = prepare_errors(make_forecasts(("a",), (1,), n_origins=48))
    out = compute_metrics_by_slice(
        errors,
        [
            ("inicio", date(2012, 1, 1), date(2013, 12, 31)),
            ("vazio", date(1990, 1, 1), date(1990, 12, 31)),
        ],
    )
    assert out["slice"].unique().to_list() == ["inicio"]
    assert out["n"][0] == 23  # alvos de fev/2012 a dez/2013


def test_slices_empty_result_has_schema():
    errors = prepare_errors(make_forecasts(("a",), (1,), n_origins=12))
    out = compute_metrics_by_slice(errors, [("nada", date(1990, 1, 1), date(1990, 12, 31))])
    assert out.is_empty()
    assert "rmse" in out.columns


def test_worst_errors_sorted_descending():
    errors = prepare_errors(make_forecasts(("a",), (1,), n_origins=48))
    worst = find_worst_errors(errors, "a", 5)
    assert worst.height == 5
    assert worst["error"].abs().is_sorted(descending=True)
