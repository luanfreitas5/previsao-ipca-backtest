"""Construtores de dados sintéticos para os testes (nunca dados reais)."""

from datetime import date, timedelta

import numpy as np
import polars as pl

from features.dataset import build_supervised_frame
from utils.dates import add_months, generate_month_ends, month_end

SERIES_LAGS = {"ipca": 10, "igpm": 0, "ibcbr": 50}
SERIES_NAMES = list(SERIES_LAGS)
N_LAGS = 12
LEDGER_SCHEMA = {
    "series": pl.String,
    "period": pl.Date,
    "value": pl.Float64,
    "available_at": pl.Date,
}


def make_ledger(n_months: int = 72, seed: int = 0, start: date = date(2014, 1, 1)) -> pl.DataFrame:
    """Ledger sintético com 3 séries, atrasos de divulgação distintos e valores aleatórios."""
    rng = np.random.default_rng(seed)
    rows = []
    for name, lag in SERIES_LAGS.items():
        for i in range(n_months):
            period = add_months(start, i)
            rows.append(
                {
                    "series": name,
                    "period": period,
                    "value": float(rng.normal(0.5, 0.3)),
                    "available_at": month_end(period) + timedelta(days=lag),
                }
            )
    return pl.DataFrame(rows, schema=LEDGER_SCHEMA)


def make_focus(start: date = date(2013, 12, 1), months: int = 80) -> pl.DataFrame:
    """Focus sintético: um snapshot por mês, 4 dias antes do fim do mês, com 14 meses-alvo."""
    rows = []
    for i in range(months):
        survey = month_end(add_months(start, i)) - timedelta(days=4)
        rows.extend(
            {
                "survey_date": survey,
                "reference_month": add_months(survey, k),
                "median": 0.4 + 0.01 * k,
            }
            for k in range(14)
        )
    return pl.DataFrame(
        rows,
        schema={"survey_date": pl.Date, "reference_month": pl.Date, "median": pl.Float64},
    )


def make_supervised(
    ledger: pl.DataFrame | None = None,
    horizons: tuple[int, ...] = (1, 3),
    origins: list[date] | None = None,
) -> pl.DataFrame:
    """Tabela supervisionada sintética sobre o ledger e o Focus de teste."""
    ledger = make_ledger() if ledger is None else ledger
    origins = origins or generate_month_ends(date(2014, 2, 1), date(2019, 12, 31))
    return build_supervised_frame(
        ledger, make_focus(), origins, horizons, SERIES_NAMES, N_LAGS, 3, 10
    )


def make_forecasts(
    models: tuple[str, ...], horizons: tuple[int, ...], n_origins: int = 96, seed: int = 0
) -> pl.DataFrame:
    """Previsões sintéticas em formato longo (um viés por modelo) para testar métricas/relatório."""
    rng = np.random.default_rng(seed)
    origins = generate_month_ends(date(2012, 1, 31), add_months(date(2012, 1, 31), n_origins - 1))
    rows = []
    for k, model in enumerate(models):
        for horizon in horizons:
            for origin in origins:
                target = add_months(origin, horizon)
                truth = float(np.sin(target.month) * 0.3 + 0.5)
                rows.append(
                    {
                        "model": model,
                        "origin": origin,
                        "horizon": horizon,
                        "target_period": target,
                        "target_available_at": month_end(target) + timedelta(days=10),
                        "y_true": truth,
                        "y_pred": truth + float(rng.normal(0, 0.1 * (k + 1))),
                    }
                )
    return pl.DataFrame(
        rows,
        schema={
            "model": pl.String,
            "origin": pl.Date,
            "horizon": pl.Int64,
            "target_period": pl.Date,
            "target_available_at": pl.Date,
            "y_true": pl.Float64,
            "y_pred": pl.Float64,
        },
    )
