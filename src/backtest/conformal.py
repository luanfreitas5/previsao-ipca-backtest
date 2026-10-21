"""Intervalos conformais de previsão calibrados somente com erros já observáveis."""

import math

import numpy as np
import polars as pl


def conformal_quantile(scores: np.ndarray, alpha: float) -> float:
    """Quantil conformal split: o ``ceil((n+1)(1-alpha))``-ésimo menor escore.

    Parameters
    ----------
    scores : np.ndarray
        Escores de não conformidade (erros absolutos de calibração).
    alpha : float
        Nível de erro (0.1 gera intervalos de 90%).

    Returns
    -------
    float
        Raio do intervalo; ``nan`` se não há escores suficientes para o nível pedido.

    Examples
    --------
    >>> round(conformal_quantile(np.arange(1.0, 11.0), 0.2), 1)
    9.0
    """
    n = len(scores)
    rank = math.ceil((n + 1) * (1 - alpha))
    if n == 0 or rank > n:
        return math.nan
    return float(np.sort(scores)[rank - 1])


def add_conformal_intervals(
    forecasts: pl.DataFrame, alpha: float, min_calibration: int
) -> pl.DataFrame:
    """Adiciona ``lower`` e ``upper`` por (modelo, horizonte) usando calibração expansiva.

    Para a previsão feita na origem ``o``, o conjunto de calibração contém só os erros
    absolutos de previsões anteriores cujo alvo já havia sido DIVULGADO até ``o``
    (``target_available_at <= o``). Usar erros ainda desconhecidos seria vazamento.
    A garantia de cobertura assume trocabilidade dos resíduos, que séries
    temporais violam apenas aproximadamente (ver limitações no README).

    Parameters
    ----------
    forecasts : pl.DataFrame
        Saída de ``run_walk_forward``.
    alpha : float
        Nível de erro (0.1 = intervalo de 90%).
    min_calibration : int
        Mínimo de resíduos de calibração para emitir intervalo.

    Returns
    -------
    pl.DataFrame
        ``forecasts`` com as colunas ``lower`` e ``upper`` (nulas sem calibração suficiente).

    Examples
    --------
    >>> add_conformal_intervals(forecasts, 0.1, 24).columns[-2:]  # doctest: +SKIP
    ['lower', 'upper']
    """
    parts = [
        _intervals_for_group(group.sort("origin"), alpha, min_calibration)
        for group in forecasts.partition_by(["model", "horizon"], maintain_order=True)
    ]
    return pl.concat(parts).sort("model", "horizon", "origin")


def _intervals_for_group(group: pl.DataFrame, alpha: float, min_calibration: int) -> pl.DataFrame:
    """Calcula os limites para um único (modelo, horizonte) ordenado por origem."""
    origins = group["origin"].to_numpy()
    available = group["target_available_at"].to_numpy()
    y_pred = group["y_pred"].to_numpy().astype(float)
    y_true = group["y_true"].to_numpy().astype(float)
    scores = np.abs(y_pred - y_true)
    lower = np.full(len(group), np.nan)
    upper = np.full(len(group), np.nan)
    for i in range(len(group)):
        usable = (available <= origins[i]) & np.isfinite(scores)
        if usable.sum() < min_calibration or not np.isfinite(y_pred[i]):
            continue
        radius = conformal_quantile(scores[usable], alpha)
        lower[i], upper[i] = y_pred[i] - radius, y_pred[i] + radius
    return group.with_columns(
        pl.Series("lower", lower).fill_nan(None), pl.Series("upper", upper).fill_nan(None)
    )


def compute_coverage(intervals: pl.DataFrame) -> pl.DataFrame:
    """Cobertura empírica e largura média dos intervalos por (modelo, horizonte).

    Parameters
    ----------
    intervals : pl.DataFrame
        Saída de ``add_conformal_intervals``.

    Returns
    -------
    pl.DataFrame
        ``model``, ``horizon``, ``n``, ``coverage``, ``mean_width``.

    Examples
    --------
    >>> compute_coverage(intervals)  # doctest: +SKIP
    """
    return (
        intervals.drop_nulls(["lower", "upper", "y_true"])
        .with_columns(
            pl.col("y_true").is_between(pl.col("lower"), pl.col("upper")).alias("_covered"),
            (pl.col("upper") - pl.col("lower")).alias("_width"),
        )
        .group_by("model", "horizon")
        .agg(
            pl.len().alias("n"),
            pl.col("_covered").mean().alias("coverage"),
            pl.col("_width").mean().alias("mean_width"),
        )
        .sort("horizon", "model")
    )
