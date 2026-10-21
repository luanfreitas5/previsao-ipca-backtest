"""Figuras do relatório: erro por horizonte, previsões vs realizado e cobertura conformal."""

import matplotlib.pyplot as plt
import polars as pl
from matplotlib.figure import Figure

from visualization.theme import apply_theme, color_for


def plot_rmse_by_horizon(metrics: pl.DataFrame) -> Figure:
    """RMSE por horizonte com IC de 95% (bootstrap em blocos), um traço por modelo.

    Parameters
    ----------
    metrics : pl.DataFrame
        Saída de ``compute_metrics``.

    Returns
    -------
    Figure
        Figura pronta para ``save_figure``.

    Examples
    --------
    >>> fig = plot_rmse_by_horizon(metrics)  # doctest: +SKIP
    """
    apply_theme()
    fig, ax = plt.subplots(figsize=(9, 5))
    for model in metrics["model"].unique(maintain_order=True).to_list():
        part = metrics.filter(pl.col("model") == model).sort("horizon")
        color = color_for(model)
        ax.plot(part["horizon"], part["rmse"], marker="o", label=model, color=color)
        ax.fill_between(part["horizon"], part["rmse_lo"], part["rmse_hi"], alpha=0.12, color=color)
    ax.set_title("RMSE do IPCA mensal por horizonte (amostra comum, IC 95%)")
    ax.set_xlabel("Horizonte (meses à frente do mês de origem)")
    ax.set_ylabel("RMSE (pontos percentuais)")
    ax.legend(title="Modelo")
    fig.tight_layout()
    return fig


def plot_forecasts_vs_actual(forecasts: pl.DataFrame, horizon: int, models: list[str]) -> Figure:
    """Série realizada e previsões de alguns modelos para um horizonte.

    Parameters
    ----------
    forecasts : pl.DataFrame
        Previsões com ``model``, ``horizon``, ``target_period``, ``y_true``, ``y_pred``.
    horizon : int
        Horizonte a plotar.
    models : list[str]
        Modelos a sobrepor.

    Returns
    -------
    Figure
        Figura pronta para ``save_figure``.

    Examples
    --------
    >>> fig = plot_forecasts_vs_actual(forecasts, 3, ["focus", "arima"])  # doctest: +SKIP
    """
    apply_theme()
    fig, ax = plt.subplots(figsize=(11, 5))
    subset = forecasts.filter(pl.col("horizon") == horizon)
    actual = subset.unique("target_period").sort("target_period")
    ax.plot(actual["target_period"], actual["y_true"], color="black", lw=2, label="IPCA realizado")
    for model in models:
        part = subset.filter(pl.col("model") == model).drop_nulls("y_pred").sort("target_period")
        ax.plot(part["target_period"], part["y_pred"], lw=1.3, label=model, color=color_for(model))
    ax.set_title(f"IPCA mensal: realizado vs previsto (horizonte {horizon} mês(es))")
    ax.set_xlabel("Mês-alvo")
    ax.set_ylabel("IPCA (% a.m.)")
    ax.legend()
    fig.tight_layout()
    return fig


def plot_conformal_coverage(coverage: pl.DataFrame, nominal: float) -> Figure:
    """Cobertura empírica dos intervalos conformais por horizonte vs. nível nominal.

    Parameters
    ----------
    coverage : pl.DataFrame
        Saída de ``compute_coverage``.
    nominal : float
        Cobertura nominal (ex.: 0.90).

    Returns
    -------
    Figure
        Figura pronta para ``save_figure``.

    Examples
    --------
    >>> fig = plot_conformal_coverage(coverage, 0.9)  # doctest: +SKIP
    """
    apply_theme()
    fig, ax = plt.subplots(figsize=(9, 5))
    for model in coverage["model"].unique(maintain_order=True).to_list():
        part = coverage.filter(pl.col("model") == model).sort("horizon")
        ax.plot(part["horizon"], part["coverage"], marker="o", label=model, color=color_for(model))
    ax.axhline(nominal, color="black", ls="--", label=f"nominal ({nominal:.0%})")
    ax.set_ylim(0, 1.02)
    ax.set_title("Cobertura empírica dos intervalos conformais")
    ax.set_xlabel("Horizonte (meses)")
    ax.set_ylabel("Cobertura empírica")
    ax.legend()
    fig.tight_layout()
    return fig
