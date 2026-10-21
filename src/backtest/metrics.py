"""Métricas de erro por horizonte, IC por bootstrap em blocos, fatias e piores erros."""

import math
from collections.abc import Sequence
from datetime import date

import numpy as np
import polars as pl


def prepare_errors(forecasts: pl.DataFrame) -> pl.DataFrame:
    """Remove previsões ausentes e adiciona colunas de erro.

    Parameters
    ----------
    forecasts : pl.DataFrame
        Saída de ``run_walk_forward``.

    Returns
    -------
    pl.DataFrame
        Linhas completas com ``error`` (previsto - real), ``abs_error`` e ``sq_error``.

    Examples
    --------
    >>> prepare_errors(forecasts).columns[-3:]  # doctest: +SKIP
    ['error', 'abs_error', 'sq_error']
    """
    return (
        forecasts.drop_nulls(["y_pred", "y_true"])
        .with_columns((pl.col("y_pred") - pl.col("y_true")).alias("error"))
        .with_columns(
            pl.col("error").abs().alias("abs_error"),
            (pl.col("error") ** 2).alias("sq_error"),
        )
    )


def restrict_to_common_sample(errors: pl.DataFrame) -> pl.DataFrame:
    """Mantém apenas (origem, horizonte) em que TODOS os modelos têm previsão.

    Comparar modelos em amostras diferentes é injusto (ex.: o Focus só existe
    depois de certa data); a amostra comum garante a mesma base para todos.

    Parameters
    ----------
    errors : pl.DataFrame
        Saída de ``prepare_errors``.

    Returns
    -------
    pl.DataFrame
        Subconjunto com o mesmo número de modelos em cada (origem, horizonte).

    Examples
    --------
    >>> restrict_to_common_sample(errors)  # doctest: +SKIP
    """
    n_models = errors["model"].n_unique()
    return (
        errors.with_columns(pl.len().over(["origin", "horizon"]).alias("_n"))
        .filter(pl.col("_n") == n_models)
        .drop("_n")
    )


def block_bootstrap_means(
    values: np.ndarray, block_length: int, n_boot: int, rng: np.random.Generator
) -> np.ndarray:
    """Médias de reamostras por bootstrap em blocos móveis (preserva autocorrelação).

    Erros de previsão a ``h`` passos são autocorrelacionados até ``h-1`` defasagens;
    reamostrar observações isoladas subestimaria a incerteza.

    Parameters
    ----------
    values : np.ndarray
        Série ordenada no tempo.
    block_length : int
        Tamanho do bloco (use o horizonte).
    n_boot : int
        Número de reamostras.
    rng : np.random.Generator
        Gerador aleatório (semente fixa para reprodutibilidade).

    Returns
    -------
    np.ndarray
        Vetor com ``n_boot`` médias reamostradas.

    Examples
    --------
    >>> block_bootstrap_means(np.arange(10.0), 2, 100, np.random.default_rng(0)).shape
    (100,)
    """
    n = len(values)
    block = max(1, min(block_length, n))
    n_blocks = math.ceil(n / block)
    starts = rng.integers(0, n - block + 1, size=(n_boot, n_blocks))
    index = (starts[:, :, None] + np.arange(block)).reshape(n_boot, -1)[:, :n]
    return values[index].mean(axis=1)


def compute_metrics(
    errors: pl.DataFrame, n_bootstrap: int = 1000, seed: int = 42, alpha: float = 0.05
) -> pl.DataFrame:
    """Calcula MAE, RMSE e viés por (modelo, horizonte) com IC de bootstrap em blocos.

    Parameters
    ----------
    errors : pl.DataFrame
        Saída de ``prepare_errors`` (idealmente na amostra comum).
    n_bootstrap : int, optional
        Reamostras do bootstrap, by default 1000.
    seed : int, optional
        Semente do bootstrap, by default 42.
    alpha : float, optional
        Nível do IC (0.05 = IC de 95%), by default 0.05.

    Returns
    -------
    pl.DataFrame
        ``model``, ``horizon``, ``n``, ``mae``, ``mae_lo``, ``mae_hi``, ``rmse``,
        ``rmse_lo``, ``rmse_hi``, ``bias``.

    Examples
    --------
    >>> compute_metrics(errors).columns[:4]  # doctest: +SKIP
    ['model', 'horizon', 'n', 'mae']
    """
    rng = np.random.default_rng(seed)
    rows = []
    for group in errors.sort("origin").partition_by(["model", "horizon"], maintain_order=True):
        horizon = int(group["horizon"][0])
        abs_err = group["abs_error"].to_numpy()
        sq_err = group["sq_error"].to_numpy()
        mae_lo, mae_hi = np.quantile(
            block_bootstrap_means(abs_err, horizon, n_bootstrap, rng), [alpha / 2, 1 - alpha / 2]
        )
        mse_lo, mse_hi = np.quantile(
            block_bootstrap_means(sq_err, horizon, n_bootstrap, rng), [alpha / 2, 1 - alpha / 2]
        )
        rows.append(
            {
                "model": group["model"][0],
                "horizon": horizon,
                "n": group.height,
                "mae": float(abs_err.mean()),
                "mae_lo": float(mae_lo),
                "mae_hi": float(mae_hi),
                "rmse": float(np.sqrt(sq_err.mean())),
                "rmse_lo": float(np.sqrt(mse_lo)),
                "rmse_hi": float(np.sqrt(mse_hi)),
                "bias": float(group["error"].mean()),  # type: ignore[arg-type]
            }
        )
    return pl.DataFrame(rows).sort("horizon", "model")


def add_relative_rmse(metrics: pl.DataFrame, reference: str) -> pl.DataFrame:
    """Adiciona ``rmse_ratio`` = RMSE do modelo / RMSE do modelo de referência (por horizonte).

    Valores acima de 1 indicam que o modelo perde para a referência.

    Parameters
    ----------
    metrics : pl.DataFrame
        Saída de ``compute_metrics``.
    reference : str
        Nome do modelo de referência (ex.: ``"focus"``).

    Returns
    -------
    pl.DataFrame
        ``metrics`` com a coluna ``rmse_ratio``.

    Examples
    --------
    >>> add_relative_rmse(metrics, "focus")  # doctest: +SKIP
    """
    ref = metrics.filter(pl.col("model") == reference).select(
        "horizon", pl.col("rmse").alias("_ref_rmse")
    )
    return (
        metrics.join(ref, on="horizon", how="left")
        .with_columns((pl.col("rmse") / pl.col("_ref_rmse")).alias("rmse_ratio"))
        .drop("_ref_rmse")
    )


def compute_metrics_by_slice(
    errors: pl.DataFrame, slices: Sequence[tuple[str, date, date]]
) -> pl.DataFrame:
    """RMSE e MAE por (fatia, modelo, horizonte), com a fatia definida pelo mês-alvo.

    Métricas agregadas escondem períodos em que o modelo falha; a fatia
    evidencia, por exemplo, o choque inflacionário de 2021-2022.

    Parameters
    ----------
    errors : pl.DataFrame
        Saída de ``prepare_errors``.
    slices : Sequence[tuple[str, date, date]]
        ``(nome, início, fim)`` de cada subperíodo (inclusive).

    Returns
    -------
    pl.DataFrame
        ``slice``, ``model``, ``horizon``, ``n``, ``mae``, ``rmse``.

    Examples
    --------
    >>> compute_metrics_by_slice(
    ...     errors, [("2023+", date(2023, 1, 1), date(2100, 1, 1))]
    ... )  # doctest: +SKIP
    """
    parts = []
    for name, start, end in slices:
        subset = errors.filter(pl.col("target_period").is_between(start, end))
        if subset.is_empty():
            continue
        parts.append(
            subset.group_by("model", "horizon")
            .agg(
                pl.len().alias("n"),
                pl.col("abs_error").mean().alias("mae"),
                pl.col("sq_error").mean().sqrt().alias("rmse"),
            )
            .with_columns(pl.lit(name).alias("slice"))
            .select("slice", "model", "horizon", "n", "mae", "rmse")
        )
    if not parts:
        return pl.DataFrame(
            schema={
                "slice": pl.String,
                "model": pl.String,
                "horizon": pl.Int64,
                "n": pl.UInt32,
                "mae": pl.Float64,
                "rmse": pl.Float64,
            }
        )
    return pl.concat(parts).sort("slice", "horizon", "model")


def find_worst_errors(errors: pl.DataFrame, model: str, k: int) -> pl.DataFrame:
    """Lista os ``k`` maiores erros absolutos de um modelo (insumo da análise de erros).

    Parameters
    ----------
    errors : pl.DataFrame
        Saída de ``prepare_errors``.
    model : str
        Modelo a inspecionar.
    k : int
        Quantidade de linhas.

    Returns
    -------
    pl.DataFrame
        Linhas com ``origin``, ``horizon``, ``target_period``, ``y_true``, ``y_pred``,
        ``error``, ordenadas do maior para o menor erro absoluto.

    Examples
    --------
    >>> find_worst_errors(errors, "arima", 10)  # doctest: +SKIP
    """
    return (
        errors.filter(pl.col("model") == model)
        .sort("abs_error", descending=True)
        .head(k)
        .select("origin", "horizon", "target_period", "y_true", "y_pred", "error")
    )
