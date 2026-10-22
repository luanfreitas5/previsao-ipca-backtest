"""Testes dos modelos de previsão."""

import math
from datetime import date

import polars as pl
import pytest

from backtest.walk_forward import build_context
from config.settings import LightGBMParams, Settings
from exceptions.base import ConfigurationError
from features.point_in_time import get_feature_columns
from helpers import N_LAGS, SERIES_NAMES
from models.base import ForecastContext
from models.factory import build_models
from models.focus import FocusBaseline
from models.lightgbm_model import LightGBMDirect
from models.naive import NaiveLast, SeasonalNaive
from models.statistical import StatsForecastModel

ORIGIN = date(2018, 6, 30)


@pytest.fixture
def context(ledger: pl.DataFrame, supervised: pl.DataFrame) -> ForecastContext:
    ctx, _ = build_context(ORIGIN, ledger.filter(pl.col("series") == "ipca"), supervised, [1, 3])
    return ctx


def ipca_value(ledger: pl.DataFrame, period: date) -> float:
    return ledger.filter((pl.col("series") == "ipca") & (pl.col("period") == period))["value"][0]


def test_naive_last_repeats_last_published_value(context, ledger):
    forecast = NaiveLast().forecast(context)
    assert forecast == {
        1: ipca_value(ledger, date(2018, 5, 1)),
        3: ipca_value(ledger, date(2018, 5, 1)),
    }


def test_seasonal_naive_uses_same_month_of_previous_year(context, ledger):
    forecast = SeasonalNaive().forecast(context)
    assert forecast[1] == ipca_value(ledger, date(2017, 7, 1))  # alvo jul/2018
    assert forecast[3] == ipca_value(ledger, date(2017, 9, 1))  # alvo set/2018


def test_seasonal_naive_goes_back_two_years_when_needed(ledger, supervised):
    ctx, _ = build_context(ORIGIN, ledger.filter(pl.col("series") == "ipca"), supervised, [12])
    # alvo jun/2019 está a 13 passos de mai/2018 -> precisa recuar 2 anos (jun/2017)
    assert SeasonalNaive().forecast(ctx)[12] == ipca_value(ledger, date(2017, 6, 1))


def test_focus_baseline_reads_point_in_time_median(context):
    forecast = FocusBaseline().forecast(context)
    expected = dict(zip(context.test["horizon"], context.test["focus_median"], strict=True))
    assert forecast == expected


def test_focus_baseline_returns_nan_without_snapshot(context):
    blank = ForecastContext(
        context.origin,
        context.horizons,
        context.ipca_history,
        context.train,
        context.test.with_columns(pl.lit(None, dtype=pl.Float64).alias("focus_median")),
    )
    assert all(math.isnan(v) for v in FocusBaseline().forecast(blank).values())


def lightgbm_params(**overrides) -> LightGBMParams:
    base = {
        "num_boost_round": 10,
        "learning_rate": 0.1,
        "num_leaves": 4,
        "min_data_in_leaf": 5,
        "feature_fraction": 1.0,
        "bagging_fraction": 1.0,
        "bagging_freq": 0,
        "lambda_l2": 0.0,
        "min_train_rows": 20,
    }
    return LightGBMParams(**{**base, **overrides})


def test_lightgbm_predicts_finite_and_is_deterministic(context):
    columns = get_feature_columns(SERIES_NAMES, N_LAGS)
    first = LightGBMDirect(lightgbm_params(), columns, seed=7).forecast(context)
    second = LightGBMDirect(lightgbm_params(), columns, seed=7).forecast(context)
    assert first == second
    assert all(math.isfinite(v) for v in first.values())


def test_lightgbm_returns_nan_with_too_few_training_rows(context):
    columns = get_feature_columns(SERIES_NAMES, N_LAGS)
    model = LightGBMDirect(lightgbm_params(min_train_rows=10_000), columns, seed=7)
    assert all(math.isnan(v) for v in model.forecast(context).values())


def test_lightgbm_ignores_future_targets(ledger, supervised):
    """Alterar alvos ainda não divulgados na origem não muda a previsão."""
    ipca = ledger.filter(pl.col("series") == "ipca")
    columns = get_feature_columns(SERIES_NAMES, N_LAGS)
    model = LightGBMDirect(lightgbm_params(), columns, seed=1)
    base_ctx, _ = build_context(ORIGIN, ipca, supervised, [1, 3])
    tampered_sup = supervised.with_columns(
        pl.when(pl.col("target_available_at") > ORIGIN)
        .then(pl.col("y_true") + 99)
        .otherwise(pl.col("y_true"))
        .alias("y_true")
    )
    tampered_ctx, _ = build_context(ORIGIN, ipca, tampered_sup, [1, 3])
    assert model.forecast(base_ctx) == model.forecast(tampered_ctx)


def test_statsforecast_models_forecast_every_horizon(context):
    pytest.importorskip("statsforecast")
    from models.factory import _build_arima, _build_ets

    for name, builder in (("arima", _build_arima), ("ets", _build_ets)):
        forecast = StatsForecastModel(name, lambda b=builder: b(12)).forecast(context)
        assert set(forecast) == {1, 3}
        assert all(math.isfinite(v) for v in forecast.values())


def test_factory_builds_configured_models_plus_focus(settings: Settings):
    models = build_models(settings, ["ipca_lag0"])
    assert [m.name for m in models] == [*settings.backtest.models, "focus"]


def test_factory_rejects_unknown_model(settings: Settings):
    broken = settings.model_copy(
        update={"backtest": settings.backtest.model_copy(update={"models": ["xyz"]})}
    )
    with pytest.raises(ConfigurationError):
        build_models(broken, [])
