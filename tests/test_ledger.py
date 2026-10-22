"""Testes do ledger point-in-time (agregação, transformação e disponibilidade)."""

from datetime import date, timedelta

import polars as pl
import pytest

from config.settings import SeriesConfig
from exceptions.data import DataValidationError
from features.ledger import add_availability, aggregate_to_monthly, apply_transform, build_ledger
from schemas.datasets import validate_ledger


def make_config(**overrides) -> SeriesConfig:
    base = {
        "name": "x",
        "sgs_code": 1,
        "frequency": "daily",
        "aggregation": "mean",
        "transform": "level",
        "release_lag_days": 0,
        "description": "teste",
    }
    return SeriesConfig(**{**base, **overrides})


def daily_frame(start: date, end: date) -> pl.DataFrame:
    days = (end - start).days + 1
    dates = [start + timedelta(days=i) for i in range(days)]
    return pl.DataFrame({"date": dates, "value": [float(d.day) for d in dates]})


def test_daily_mean_and_incomplete_month_dropped():
    # janeiro completo; fevereiro vai só até o dia 10 -> descartado
    df = daily_frame(date(2020, 1, 1), date(2020, 2, 10))
    monthly = aggregate_to_monthly(df, make_config(aggregation="mean"))
    assert monthly["period"].to_list() == [date(2020, 1, 1)]
    assert monthly["value"][0] == pytest.approx(16.0)


def test_daily_last_uses_last_observation_of_month():
    df = daily_frame(date(2020, 1, 1), date(2020, 1, 31))
    monthly = aggregate_to_monthly(df, make_config(aggregation="last"))
    assert monthly["value"][0] == 31.0


def test_month_ending_on_weekend_is_still_complete():
    # último dado em 29/05 (sexta); fim do mês em 31/05 (domingo)
    df = daily_frame(date(2020, 5, 1), date(2020, 5, 29))
    assert aggregate_to_monthly(df, make_config()).height == 1


def test_pct_change_uses_only_current_and_previous_month():
    monthly = pl.DataFrame(
        {
            "period": [date(2020, 1, 1), date(2020, 2, 1), date(2020, 3, 1)],
            "value": [100.0, 110.0, 99.0],
        }
    )
    out = apply_transform(monthly, "pct_change")
    assert out["value"].to_list() == pytest.approx([10.0, -10.0])
    assert out["period"].to_list() == [date(2020, 2, 1), date(2020, 3, 1)]


def test_diff_and_unknown_transform():
    monthly = pl.DataFrame({"period": [date(2020, 1, 1), date(2020, 2, 1)], "value": [1.0, 3.0]})
    assert apply_transform(monthly, "diff")["value"].to_list() == [2.0]
    with pytest.raises(ValueError):
        apply_transform(monthly, "log")


def test_availability_is_month_end_plus_lag():
    monthly = pl.DataFrame({"period": [date(2020, 2, 1)], "value": [1.0]})
    out = add_availability(monthly, 10)
    assert out["available_at"][0] == date(2020, 3, 10)  # 29/02 + 10 dias


def test_build_ledger_matches_catalog_and_validates():
    sgs = pl.concat(
        [
            daily_frame(date(2020, 1, 1), date(2020, 4, 30)).with_columns(
                pl.lit("fx").alias("series")
            ),
            pl.DataFrame(
                {"date": [date(2020, m, 1) for m in (1, 2, 3, 4)], "value": [0.2, 0.3, 0.1, 0.4]}
            ).with_columns(pl.lit("ipca").alias("series")),
        ]
    )
    configs = [
        make_config(name="ipca", frequency="monthly", aggregation="last", release_lag_days=10),
        make_config(name="fx", transform="pct_change"),
    ]
    ledger = build_ledger(sgs, configs)
    assert set(ledger["series"]) == {"ipca", "fx"}
    ipca_jan = ledger.filter((pl.col("series") == "ipca") & (pl.col("period") == date(2020, 1, 1)))
    assert ipca_jan["available_at"][0] == date(2020, 2, 10)


def test_ledger_with_gap_is_rejected():
    ledger = pl.DataFrame(
        {
            "series": ["ipca"] * 2,
            "period": [date(2020, 1, 1), date(2020, 3, 1)],
            "value": [0.1, 0.2],
            "available_at": [date(2020, 2, 10), date(2020, 4, 10)],
        }
    )
    with pytest.raises(DataValidationError):
        validate_ledger(ledger)


def test_ledger_with_availability_before_period_end_is_rejected():
    ledger = pl.DataFrame(
        {
            "series": ["ipca"],
            "period": [date(2020, 1, 1)],
            "value": [0.1],
            "available_at": [date(2020, 1, 15)],
        }
    )
    with pytest.raises(DataValidationError):
        validate_ledger(ledger)
