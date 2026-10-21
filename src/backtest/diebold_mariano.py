"""Teste de Diebold-Mariano (1995) com correção de Harvey-Leybourne-Newbold (1997)."""

import logging
import math
from dataclasses import dataclass
from typing import Literal

import numpy as np
import polars as pl
from scipy import stats

logger = logging.getLogger(__name__)

Loss = Literal["squared", "absolute"]
Alternative = Literal["two-sided", "less", "greater"]


@dataclass(frozen=True)
class DMResult:
    """Resultado do teste de Diebold-Mariano.

    Attributes
    ----------
    statistic : float
        Estatística (com correção HLN). Negativa = modelo A mais acurado que B.
    p_value : float
        Valor-p conforme a hipótese alternativa escolhida.
    mean_diff : float
        Média do diferencial de perdas ``L(e_A) - L(e_B)``.
    n : int
        Número de pares de previsões.
    """

    statistic: float
    p_value: float
    mean_diff: float
    n: int


def _long_run_variance(diff: np.ndarray, horizon: int) -> float:
    """Variância de longo prazo de ``d`` com autocovariâncias até ``horizon - 1``."""
    n = len(diff)
    centered = diff - diff.mean()
    variance = float(centered @ centered) / n
    for lag in range(1, horizon):
        variance += 2 * float(centered[lag:] @ centered[:-lag]) / n
    return variance / n


def diebold_mariano(
    errors_a: np.ndarray,
    errors_b: np.ndarray,
    horizon: int = 1,
    loss: Loss = "squared",
    alternative: Alternative = "two-sided",
) -> DMResult:
    """Testa H0: os modelos A e B têm a mesma acurácia preditiva.

    O diferencial ``d_t = L(e_A,t) - L(e_B,t)`` tem autocorrelação até ``h-1`` em
    previsões a ``h`` passos; a variância usa essas autocovariâncias e a estatística
    recebe a correção de amostra pequena de Harvey et al. (1997), com cauda t(n-1).

    Parameters
    ----------
    errors_a, errors_b : np.ndarray
        Erros de previsão dos modelos A e B, pareados e ordenados no tempo.
    horizon : int, optional
        Horizonte de previsão ``h`` (define quantas autocovariâncias entram), by default 1.
    loss : {"squared", "absolute"}, optional
        Função de perda, by default ``"squared"``.
    alternative : {"two-sided", "less", "greater"}, optional
        ``"less"``: A é mais acurado que B; ``"greater"``: A é menos acurado.

    Returns
    -------
    DMResult
        Estatística, valor-p, diferença média e tamanho amostral. ``nan`` se a
        amostra for curta demais ou o diferencial for degenerado (variância <= 0).

    Raises
    ------
    ValueError
        Se os vetores tiverem tamanhos diferentes ou ``horizon < 1``.

    Examples
    --------
    >>> rng = np.random.default_rng(0)
    >>> a, b = rng.normal(0, 1, 100), rng.normal(0, 2, 100)
    >>> diebold_mariano(a, b, horizon=1, alternative="less").p_value < 0.05
    True
    """
    if len(errors_a) != len(errors_b):
        raise ValueError("Os vetores de erros devem ter o mesmo tamanho")
    if horizon < 1:
        raise ValueError("horizon deve ser >= 1")
    n = len(errors_a)
    func = np.square if loss == "squared" else np.abs
    diff = func(errors_a) - func(errors_b)
    mean_diff = float(diff.mean()) if n else math.nan
    if n <= 2 * horizon:
        return DMResult(math.nan, math.nan, mean_diff, n)
    variance = _long_run_variance(diff, horizon)
    if variance <= 0:
        return DMResult(math.nan, math.nan, mean_diff, n)
    correction = math.sqrt((n + 1 - 2 * horizon + horizon * (horizon - 1) / n) / n)
    statistic = correction * mean_diff / math.sqrt(variance)
    dist = stats.t(df=n - 1)
    p_value = {
        "two-sided": 2 * dist.sf(abs(statistic)),
        "less": dist.cdf(statistic),
        "greater": dist.sf(statistic),
    }[alternative]
    return DMResult(float(statistic), float(p_value), mean_diff, n)


def run_dm_against_reference(
    errors: pl.DataFrame, reference: str, loss: Loss = "squared"
) -> pl.DataFrame:
    """Aplica Diebold-Mariano de cada modelo contra a referência, por horizonte.

    Parameters
    ----------
    errors : pl.DataFrame
        Saída de ``prepare_errors`` (``model``, ``origin``, ``horizon``, ``error``).
    reference : str
        Modelo de referência (ex.: ``"focus"``), usado como B.
    loss : {"squared", "absolute"}, optional
        Função de perda, by default ``"squared"``.

    Returns
    -------
    pl.DataFrame
        ``model``, ``horizon``, ``loss``, ``n``, ``mean_diff``, ``dm_stat``, ``p_value``.
        ``dm_stat < 0`` indica modelo mais acurado que a referência.

    Examples
    --------
    >>> run_dm_against_reference(errors, "focus")  # doctest: +SKIP
    """
    ref = errors.filter(pl.col("model") == reference).select(
        "origin", "horizon", pl.col("error").alias("ref_error")
    )
    rows = []
    others = errors.filter(pl.col("model") != reference)
    for group in others.partition_by(["model", "horizon"], maintain_order=True):
        paired = group.join(ref, on=["origin", "horizon"], how="inner").sort("origin")
        horizon = int(group["horizon"][0])
        result = diebold_mariano(
            paired["error"].to_numpy(), paired["ref_error"].to_numpy(), horizon, loss
        )
        rows.append(
            {
                "model": group["model"][0],
                "horizon": horizon,
                "loss": loss,
                "n": result.n,
                "mean_diff": result.mean_diff,
                "dm_stat": result.statistic,
                "p_value": result.p_value,
            }
        )
    schema = {
        "model": pl.String,
        "horizon": pl.Int64,
        "loss": pl.String,
        "n": pl.Int64,
        "mean_diff": pl.Float64,
        "dm_stat": pl.Float64,
        "p_value": pl.Float64,
    }
    return pl.DataFrame(rows, schema=schema).sort("horizon", "model")
