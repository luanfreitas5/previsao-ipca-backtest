"""Tema visual compartilhado e persistência de figuras."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # backend sem janela: seguro em CI e servidores

import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib.figure import Figure

PALETTE: dict[str, str] = {
    "focus": "#d62728",
    "naive_last": "#7f7f7f",
    "naive_seasonal": "#bcbd22",
    "arima": "#1f77b4",
    "ets": "#2ca02c",
    "lightgbm": "#9467bd",
}
DEFAULT_COLOR = "#17becf"


def apply_theme() -> None:
    """Aplica o estilo seaborn padrão do projeto.

    Examples
    --------
    >>> apply_theme()
    """
    sns.set_theme(style="whitegrid", context="notebook")
    plt.rcParams["figure.dpi"] = 120


def color_for(model: str) -> str:
    """Cor do modelo na paleta compartilhada (cor padrão se desconhecido).

    Parameters
    ----------
    model : str
        Nome do modelo.

    Returns
    -------
    str
        Cor hexadecimal.

    Examples
    --------
    >>> color_for("focus")
    '#d62728'
    """
    return PALETTE.get(model, DEFAULT_COLOR)


def save_figure(fig: Figure, directory: Path, name: str) -> list[Path]:
    """Salva a figura em PNG (300 dpi) e SVG e a fecha.

    Parameters
    ----------
    fig : Figure
        Figura a salvar.
    directory : Path
        Diretório de destino (criado se necessário).
    name : str
        Nome-base dos arquivos, sem extensão.

    Returns
    -------
    list[Path]
        Caminhos do PNG e do SVG.

    Examples
    --------
    >>> save_figure(fig, Path("reports/figures"), "rmse")  # doctest: +SKIP
    """
    directory.mkdir(parents=True, exist_ok=True)
    paths = [directory / f"{name}.png", directory / f"{name}.svg"]
    fig.savefig(paths[0], dpi=300, bbox_inches="tight")
    fig.savefig(paths[1], bbox_inches="tight")
    plt.close(fig)
    return paths
