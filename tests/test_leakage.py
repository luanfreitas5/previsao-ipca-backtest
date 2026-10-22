"""Testes de ausência de vazamento temporal nas features e na tabela supervisionada."""

from datetime import date, timedelta

import polars as pl
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from features.dataset import attach_focus, build_supervised_frame
from features.point_in_time import add_derived_features, build_feature_frame, get_feature_columns
from helpers import N_LAGS, SERIES_NAMES, make_focus, make_ledger
from utils.dates import add_months

LEDGER = make_ledger()
pytestmark = pytest.mark.leakage


def features_at(ledger: pl.DataFrame, origin: date) -> pl.DataFrame:
    return build_feature_frame(ledger, [origin], SERIES_NAMES, N_LAGS)


def test_latest_observation_respects_release_lag():
    row = features_at(LEDGER, date(2017, 6, 30)).row(0, named=True)
    assert row["ipca_last_period"] == date(2017, 5, 1)  # junho só sai em 10/07
    assert row["ibcbr_last_period"] == date(2017, 4, 1)  # ~50 dias de atraso
    assert row["igpm_last_period"] == date(2017, 6, 1)  # sem atraso


def test_lags_point_to_earlier_months():
    row = features_at(LEDGER, date(2017, 6, 30)).row(0, named=True)
    values = dict(
        zip(
            LEDGER.filter(pl.col("series") == "ipca")["period"],
            LEDGER.filter(pl.col("series") == "ipca")["value"],
            strict=True,
        )
    )
    assert row["ipca_lag0"] == values[date(2017, 5, 1)]
    assert row["ipca_lag3"] == values[date(2017, 2, 1)]


@given(offset=st.integers(min_value=0, max_value=1500))
@settings(max_examples=40, deadline=None, suppress_health_check=[HealthCheck.too_slow])
def test_every_lag_was_public_at_origin(offset: int):
    """Propriedade: toda observação usada como lag já havia sido divulgada na origem."""
    origin = date(2015, 1, 1) + timedelta(days=offset)
    row = features_at(LEDGER, origin).row(0, named=True)
    for name in SERIES_NAMES:
        last = row[f"{name}_last_period"]
        if last is None:
            continue
        available = dict(
            LEDGER.filter(pl.col("series") == name).select("period", "available_at").iter_rows()
        )
        for lag in range(N_LAGS):
            period = add_months(last, -lag)
            if period in available:
                assert available[period] <= origin
        assert available[last] <= origin
        later = add_months(last, 1)
        assert later not in available or available[later] > origin  # o próximo ainda não saiu


def test_features_invariant_to_future_values():
    """Alterar valores divulgados DEPOIS da origem não pode mudar as features."""
    origin = date(2017, 6, 30)
    tampered = LEDGER.with_columns(
        pl.when(pl.col("available_at") > origin)
        .then(pl.col("value") + 1000.0)
        .otherwise(pl.col("value"))
        .alias("value")
    )
    assert features_at(tampered, origin).equals(features_at(LEDGER, origin))


def test_features_invariant_to_removing_future_rows():
    origin = date(2017, 6, 30)
    truncated = LEDGER.filter(pl.col("available_at") <= origin)
    assert features_at(truncated, origin).equals(features_at(LEDGER, origin))


def test_derived_features_use_only_lags():
    frame = add_derived_features(features_at(LEDGER, date(2017, 6, 30)))
    lags = [frame[f"ipca_lag{j}"][0] for j in range(12)]
    expected = 1.0
    for value in lags:
        expected *= 1 + value / 100
    assert frame["ipca_acc12"][0] == pytest.approx((expected - 1) * 100)
    assert frame["ipca_mean3"][0] == pytest.approx(sum(lags[:3]) / 3)


def test_supervised_target_is_known_only_after_availability(supervised: pl.DataFrame):
    row = supervised.filter((pl.col("origin") == date(2017, 6, 30)) & (pl.col("horizon") == 1)).row(
        0, named=True
    )
    assert row["target_period"] == date(2017, 7, 1)
    assert row["target_available_at"] == date(2017, 8, 10)
    assert row["target_available_at"] > row["origin"]


def test_steps_ahead_counts_from_last_published_month(supervised: pl.DataFrame):
    rows = supervised.filter(pl.col("origin") == date(2017, 6, 30)).sort("horizon")
    # último IPCA divulgado: maio/2017 -> h=1 (julho) está 2 passos à frente; h=3 (setembro), 4
    assert rows["steps_ahead"].to_list() == [2, 4]


def test_supervised_features_ignore_future_values():
    origin = date(2017, 6, 30)
    focus = make_focus()
    args = ([origin], [1, 3], SERIES_NAMES, N_LAGS, 3, 10)
    base = build_supervised_frame(LEDGER, focus, *args)
    tampered_ledger = LEDGER.with_columns(
        pl.when(pl.col("available_at") > origin)
        .then(pl.col("value") + 1000.0)
        .otherwise(pl.col("value"))
        .alias("value")
    )
    tampered = build_supervised_frame(tampered_ledger, focus, *args)
    columns = [*get_feature_columns(SERIES_NAMES, N_LAGS), "focus_median"]
    assert tampered.select(columns).equals(base.select(columns))


def frame_for_focus(origin: date) -> pl.DataFrame:
    return pl.DataFrame({"origin": [origin], "target_period": [date(2017, 7, 1)]})


def focus_frame(survey: date) -> pl.DataFrame:
    return pl.DataFrame(
        {"survey_date": [survey], "reference_month": [date(2017, 7, 1)], "median": [0.33]}
    )


def test_focus_snapshot_is_used_when_public_and_fresh():
    out = attach_focus(frame_for_focus(date(2017, 6, 30)), focus_frame(date(2017, 6, 26)), 3, 10)
    assert out["focus_median"][0] == pytest.approx(0.33)


def test_focus_snapshot_not_yet_published_is_ignored():
    # snapshot de 29/06 só é divulgado em 02/07 (> origem 30/06)
    out = attach_focus(frame_for_focus(date(2017, 6, 30)), focus_frame(date(2017, 6, 29)), 3, 10)
    assert out["focus_median"][0] is None


def test_stale_focus_snapshot_is_dropped():
    out = attach_focus(frame_for_focus(date(2017, 6, 30)), focus_frame(date(2017, 6, 10)), 3, 10)
    assert out["focus_median"][0] is None
