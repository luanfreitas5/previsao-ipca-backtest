"""Testes da aritmética de meses."""

from datetime import date

import pytest
from hypothesis import given
from hypothesis import strategies as st

from utils.dates import add_months, generate_month_ends, month_end, months_between

DATES = st.dates(min_value=date(1990, 1, 1), max_value=date(2060, 12, 31))


@pytest.mark.smoke
def test_month_end_handles_leap_year():
    assert month_end(date(2020, 2, 10)) == date(2020, 2, 29)
    assert month_end(date(2021, 2, 10)) == date(2021, 2, 28)


@given(value=DATES, months=st.integers(-240, 240))
def test_add_months_roundtrip(value, months):
    """Invariante: deslocar e medir devolve o mesmo número de meses."""
    shifted = add_months(value, months)
    assert shifted.day == 1
    assert months_between(value, shifted) == months


@given(first=DATES, count=st.integers(0, 60))
def test_generate_month_ends_is_consecutive(first, count):
    last = add_months(first, count)
    ends = generate_month_ends(first, last)
    assert len(ends) == count + 1
    assert all(e == month_end(e) for e in ends)
    assert ends == sorted(ends)


def test_generate_month_ends_empty_when_reversed():
    assert generate_month_ends(date(2020, 5, 1), date(2020, 1, 1)) == []
