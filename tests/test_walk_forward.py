"""Testes do motor de backtest walk-forward e da guarda contra vazamento."""

import math
from datetime import date
from typing import cast

import polars as pl
import pytest

from backtest.walk_forward import assert_no_leakage, build_context, run_walk_forward
from exceptions.data import LeakageError
from helpers import make_ledger, make_supervised
from models.base import ForecastContext, Forecaster
from models.naive import NaiveLast
from utils.dates import generate_month_ends

pytestmark = pytest.mark.leakage
ORIGINS = generate_month_ends(date(2017, 1, 31), date(2018, 12, 31))


class Recorder(Forecaster):
    """Modelo que só registra os contextos recebidos."""

    name = "recorder"

    def __init__(self) -> None:
        self.contexts: list[ForecastContext] = []

    def forecast(self, context: ForecastContext) -> dict[int, float]:
        self.contexts.append(context)
        return dict.fromkeys(context.horizons, 0.5)


class Exploding(Forecaster):
    name = "exploding"

    def forecast(self, context: ForecastContext) -> dict[int, float]:
        raise ValueError("falha proposital")


class WithNan(Forecaster):
    name = "with_nan"

    def forecast(self, context: ForecastContext) -> dict[int, float]:
        return dict.fromkeys(context.horizons, math.nan)


def test_every_context_contains_only_public_information(ledger, supervised):
    recorder = Recorder()
    run_walk_forward(supervised, ledger, [recorder], ORIGINS, show_progress=False)
    assert recorder.contexts
    for ctx in recorder.contexts:
        assert cast("date", ctx.ipca_history["available_at"].max()) <= ctx.origin
        assert cast("date", ctx.train["target_available_at"].max()) <= ctx.origin
        assert (ctx.train["origin"] < ctx.origin).all()
        assert set(ctx.test["origin"]) == {ctx.origin}
        assert "y_true" not in ctx.test.columns
        assert "target_available_at" not in ctx.test.columns


def test_training_window_is_expanding(ledger, supervised):
    recorder = Recorder()
    run_walk_forward(supervised, ledger, [recorder], ORIGINS, show_progress=False)
    sizes = [ctx.train.height for ctx in recorder.contexts]
    assert sizes == sorted(sizes)
    assert sizes[-1] > sizes[0]


def test_assert_no_leakage_detects_future_training_target(ledger, supervised):
    origin = date(2017, 6, 30)
    context, _ = build_context(
        origin, ledger.filter(pl.col("series") == "ipca"), supervised, [1, 3]
    )
    future_row = supervised.filter(pl.col("target_available_at") > origin).head(1)
    leaky = ForecastContext(
        origin,
        context.horizons,
        context.ipca_history,
        pl.concat([context.train, future_row]),
        context.test,
    )
    with pytest.raises(LeakageError):
        assert_no_leakage(leaky)


def test_assert_no_leakage_detects_future_history(ledger, supervised):
    origin = date(2017, 6, 30)
    ipca = ledger.filter(pl.col("series") == "ipca")
    context, _ = build_context(origin, ipca, supervised, [1, 3])
    leaky = ForecastContext(origin, context.horizons, ipca, context.train, context.test)
    with pytest.raises(LeakageError):
        assert_no_leakage(leaky)


def test_results_are_paired_with_realized_values(ledger, supervised):
    result = run_walk_forward(supervised, ledger, [NaiveLast()], ORIGINS, show_progress=False)
    assert result["y_pred"].null_count() == 0
    ipca = {
        r["period"]: r["value"]
        for r in ledger.filter(pl.col("series") == "ipca").iter_rows(named=True)
    }
    for row in result.iter_rows(named=True):
        assert row["y_true"] == ipca[row["target_period"]]


def test_failing_and_nan_models_yield_null_predictions(ledger, supervised):
    result = run_walk_forward(
        supervised, ledger, [Exploding(), WithNan()], ORIGINS, show_progress=False
    )
    assert result.height > 0
    assert result["y_pred"].null_count() == result.height


def test_origins_without_realized_targets_are_skipped():
    ledger = make_ledger(n_months=30)
    supervised = make_supervised(
        ledger, origins=generate_month_ends(date(2014, 2, 1), date(2016, 6, 30))
    )
    last_origin = date(2016, 6, 30)
    result = run_walk_forward(supervised, ledger, [NaiveLast()], [last_origin], show_progress=False)
    # IPCA de jul/2016 (h=1) existe no ledger de 30 meses? 30 meses vão até jun/2016 -> nenhum alvo
    assert result.is_empty()
