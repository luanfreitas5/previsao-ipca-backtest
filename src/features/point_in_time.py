"""Matriz de lags point-in-time: o que cada série mostrava em cada data de origem.

Regra central: na origem ``o``, só entram observações com ``available_at <= o``.
Como o atraso de divulgação é constante por série, o conjunto disponível é sempre
um prefixo da série; o lag ``j`` é a observação ``j`` meses antes da última disponível.
"""

from collections.abc import Sequence
from datetime import date

import polars as pl


def build_feature_frame(
    ledger: pl.DataFrame, origins: Sequence[date], series_names: Sequence[str], n_lags: int
) -> pl.DataFrame:
    """Monta, para cada origem, os ``n_lags`` valores mais recentes DISPONÍVEIS de cada série.

    Parameters
    ----------
    ledger : pl.DataFrame
        Colunas ``series``, ``period``, ``value``, ``available_at``.
    origins : Sequence[date]
        Datas de origem (normalmente fins de mês).
    series_names : Sequence[str]
        Séries a incluir, na ordem desejada das colunas.
    n_lags : int
        Número de lags (``{serie}_lag0`` é a observação mais recente divulgada).

    Returns
    -------
    pl.DataFrame
        Uma linha por origem com ``{serie}_last_period`` e ``{serie}_lag0..n-1``.
        Valores ausentes (série ainda não existia) ficam nulos.

    Examples
    --------
    >>> build_feature_frame(ledger, [date(2020, 1, 31)], ["ipca"], 3).columns  # doctest: +SKIP
    ['origin', 'ipca_last_period', 'ipca_lag0', 'ipca_lag1', 'ipca_lag2']
    """
    frame = pl.DataFrame({"origin": list(origins)}, schema={"origin": pl.Date}).sort("origin")
    for name in series_names:
        obs = (
            ledger.filter(pl.col("series") == name)
            .select("period", "value", "available_at")
            .sort("available_at")
        )
        last = frame.join_asof(
            obs.select("available_at", pl.col("period").alias(f"{name}_last_period")),
            left_on="origin",
            right_on="available_at",
            strategy="backward",
        ).select("origin", f"{name}_last_period")
        frame = frame.join(_add_lags(last, obs, name, n_lags), on="origin", how="left")
    return frame


def _add_lags(last: pl.DataFrame, obs: pl.DataFrame, name: str, n_lags: int) -> pl.DataFrame:
    """Anexa ``{name}_lag0..n-1`` buscando cada período ``j`` meses antes do último disponível."""
    wide = last
    last_col = pl.col(f"{name}_last_period")
    for lag in range(n_lags):
        lagged = obs.select(pl.col("period").alias("_p"), pl.col("value").alias(f"{name}_lag{lag}"))
        wide = (
            wide.with_columns(last_col.dt.offset_by(f"-{lag}mo").alias("_p"))
            .join(lagged, on="_p", how="left")
            .drop("_p")
        )
    return wide


def add_derived_features(frame: pl.DataFrame) -> pl.DataFrame:
    """Adiciona agregações dos lags do IPCA (acumulado em 12 meses e média de 3 meses).

    Usa só colunas de lag já point-in-time, portanto não introduz informação futura.

    Parameters
    ----------
    frame : pl.DataFrame
        Saída de ``build_feature_frame`` com ao menos 12 lags de ``ipca``.

    Returns
    -------
    pl.DataFrame
        ``frame`` com ``ipca_acc12`` (% composto) e ``ipca_mean3``.

    Examples
    --------
    >>> add_derived_features(frame).columns[-2:]  # doctest: +SKIP
    ['ipca_acc12', 'ipca_mean3']
    """
    lags12 = [f"ipca_lag{j}" for j in range(12)]
    lags3 = lags12[:3]
    compound = pl.fold(
        acc=pl.lit(1.0),
        function=lambda acc, x: acc * (1 + x / 100),
        exprs=[pl.col(c) for c in lags12],
    )
    return frame.with_columns(
        ((compound - 1) * 100).alias("ipca_acc12"),
        pl.mean_horizontal([pl.col(c) for c in lags3]).alias("ipca_mean3"),
    )


def get_feature_columns(series_names: Sequence[str], n_lags: int) -> list[str]:
    """Lista, em ordem estável, as colunas usadas como features de modelo.

    Parameters
    ----------
    series_names : Sequence[str]
        Séries do ledger.
    n_lags : int
        Número de lags por série.

    Returns
    -------
    list[str]
        Lags de cada série + derivadas + ``target_month`` + ``steps_ahead``.

    Examples
    --------
    >>> get_feature_columns(["ipca"], 2)
    ['ipca_lag0', 'ipca_lag1', 'ipca_acc12', 'ipca_mean3', 'target_month', 'steps_ahead']
    """
    lags = [f"{name}_lag{j}" for name in series_names for j in range(n_lags)]
    return [*lags, "ipca_acc12", "ipca_mean3", "target_month", "steps_ahead"]
