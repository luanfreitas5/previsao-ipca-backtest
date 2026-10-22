"""Testes da limpeza bronze -> silver e dos contratos de dados."""

from datetime import date

import polars as pl
import pytest

from data.cleaning import clean_focus, clean_sgs
from exceptions.data import DataValidationError
from schemas.datasets import FOCUS_SILVER_SCHEMA, validate_dataframe


def test_clean_sgs_types_and_sorting():
    records = [
        {"data": "01/02/2020", "valor": "0.25"},
        {"data": "01/01/2020", "valor": "0.21"},
    ]
    df = clean_sgs(records, "ipca")
    assert df.schema == {"series": pl.String, "date": pl.Date, "value": pl.Float64}
    assert df["date"].to_list() == [date(2020, 1, 1), date(2020, 2, 1)]


def test_clean_sgs_drops_invalid_rows_and_keeps_last_duplicate():
    records = [
        {"data": "01/01/2020", "valor": "0.10"},
        {"data": "01/01/2020", "valor": "0.30"},
        {"data": "01/02/2020", "valor": ""},
        {"data": "data-ruim", "valor": "1.0"},
    ]
    df = clean_sgs(records, "ipca")
    assert df.height == 1
    assert df["value"][0] == pytest.approx(0.30)


def test_clean_sgs_empty_raises():
    with pytest.raises(DataValidationError):
        clean_sgs([], "ipca")
    with pytest.raises(DataValidationError):
        clean_sgs([{"data": "x", "valor": "y"}], "ipca")


def test_clean_focus_parses_reference_month_and_optional_columns():
    records = [
        {"Data": "2020-01-06", "DataReferencia": "03/2020", "Mediana": 0.31},
        {"Data": "2020-01-06", "DataReferencia": "03/2020", "Mediana": 0.35},  # duplicata
        {"Data": "2020-01-07", "DataReferencia": "04/2020", "Mediana": None},  # sem mediana
    ]
    df = clean_focus(records)
    assert df.height == 1
    assert df["reference_month"][0] == date(2020, 3, 1)
    assert df["median"][0] == pytest.approx(0.35)
    assert df["n_respondents"][0] is None


def test_focus_contract_rejects_unexpected_column():
    df = clean_focus([{"Data": "2020-01-06", "DataReferencia": "03/2020", "Mediana": 0.31}])
    with pytest.raises(DataValidationError):
        validate_dataframe(df.with_columns(pl.lit(1).alias("extra")), FOCUS_SILVER_SCHEMA, "focus")
