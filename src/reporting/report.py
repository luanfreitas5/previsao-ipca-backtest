"""Renderiza o relatório final (pt-BR), incluindo onde os modelos perdem para o Focus."""

import math
from pathlib import Path
from typing import Any

import polars as pl

from config.settings import Settings
from reporting.analysis import Analysis

SIGNIFICANCE = 0.05


def to_markdown_table(df: pl.DataFrame, digits: int = 3) -> str:
    """Converte um DataFrame em tabela Markdown (floats arredondados).

    Parameters
    ----------
    df : pl.DataFrame
        Tabela a converter.
    digits : int, optional
        Casas decimais dos floats, by default 3.

    Returns
    -------
    str
        Tabela em formato pipe.

    Examples
    --------
    >>> print(to_markdown_table(pl.DataFrame({"a": [1.23456]}), 2))
    | a |
    | --- |
    | 1.23 |
    """
    header = "| " + " | ".join(df.columns) + " |"
    divider = "| " + " | ".join("---" for _ in df.columns) + " |"
    lines = [header, divider]
    for row in df.iter_rows():
        cells = [f"{v:.{digits}f}" if isinstance(v, float) else str(v) for v in row]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def summarize_vs_reference(analysis: Analysis, reference: str) -> list[str]:
    """Gera frases sobre onde cada modelo ganha ou perde da referência (RMSE + DM).

    Parameters
    ----------
    analysis : Analysis
        Resultados consolidados.
    reference : str
        Modelo de referência (Focus).

    Returns
    -------
    list[str]
        Uma linha por (modelo, horizonte) com veredito e valor-p.

    Examples
    --------
    >>> summarize_vs_reference(analysis, "focus")  # doctest: +SKIP
    """
    joined = analysis.metrics.filter(pl.col("model") != reference).join(
        analysis.dm_squared.select("model", "horizon", "p_value"), on=["model", "horizon"]
    )
    return [
        _verdict(row, reference) for row in joined.sort("horizon", "model").iter_rows(named=True)
    ]


def _verdict(row: dict[str, Any], reference: str) -> str:
    """Frase com o veredito de um modelo num horizonte."""
    ratio, p_value = row["rmse_ratio"], row["p_value"]
    significant = p_value is not None and not math.isnan(p_value) and p_value < SIGNIFICANCE
    if ratio > 1:
        verdict = (
            "perde significativamente para" if significant else "perde (sem significância) para"
        )
    else:
        verdict = (
            "supera significativamente" if significant else "empata/supera sem significância o"
        )
    return (
        f"- h={row['horizon']}: **{row['model']}** {verdict} {reference} "
        f"(RMSE {row['rmse']:.3f}; razão ao {reference} {ratio:.2f}; p-valor DM = {p_value:.3f})"
    )


def render_report(analysis: Analysis, settings: Settings, figure_names: list[str]) -> str:
    """Monta o texto Markdown do relatório final.

    Parameters
    ----------
    analysis : Analysis
        Resultados consolidados.
    settings : Settings
        Configuração validada.
    figure_names : list[str]
        Nomes-base das figuras já salvas em ``reports/figures``.

    Returns
    -------
    str
        Relatório completo em Markdown (pt-BR).

    Examples
    --------
    >>> text = render_report(analysis, settings, ["rmse_por_horizonte"])  # doctest: +SKIP
    """
    ref = settings.report.reference_model
    metrics_cols = ["model", "horizon", "n", "mae", "rmse", "rmse_lo", "rmse_hi", "rmse_ratio"]
    sections = [
        "# Relatório final — Previsão do IPCA mensal (backtest walk-forward)",
        f"_Versão {settings.version}. Gerado automaticamente por `python src/main.py report`._",
        "## 1. Desenho do experimento",
        f"- Origens: fins de mês de {settings.backtest.first_origin} em diante, janela expansiva.\n"
        f"- Horizontes: {settings.backtest.horizons} meses à frente do mês de origem.\n"
        f"- Referência: **{ref}** (mediana do Boletim Focus vigente na origem).\n"
        "- Todas as métricas usam a amostra comum a todos os modelos e ao Focus.",
        "## 2. Erro por horizonte (IC 95% por bootstrap em blocos)",
        to_markdown_table(analysis.metrics.select(metrics_cols)),
        "`rmse_ratio` > 1 significa pior que o Focus.",
        "## 3. Diebold-Mariano contra o Focus (perda quadrática)",
        "Estatística < 0: modelo mais acurado que o Focus. Correção HLN, cauda t.",
        to_markdown_table(analysis.dm_squared),
        "### Perda absoluta",
        to_markdown_table(analysis.dm_absolute),
        "## 4. Onde os modelos perdem para o Focus",
        "\n".join(summarize_vs_reference(analysis, ref)),
        "## 5. Avaliação por subperíodo",
        to_markdown_table(analysis.slices),
        "## 6. Intervalos conformais",
        f"Cobertura nominal: {1 - settings.backtest.alpha:.0%}. "
        "Calibração apenas com erros já divulgados na origem.",
        to_markdown_table(analysis.coverage),
        f"## 7. Maiores erros do melhor modelo (`{analysis.best_model}`)",
        to_markdown_table(analysis.worst),
        "## 8. Figuras",
        "\n".join(f"![{name}](figures/{name}.png)" for name in figure_names),
        "## 9. Limitações",
        "- O IBC-Br e as demais séries estão na revisão mais recente do SGS, não na vintage "
        "original de cada data (não há vintages em tempo real no SGS).\n"
        "- As defasagens de divulgação são aproximações conservadoras do calendário real.\n"
        "- Intervalos conformais assumem resíduos aproximadamente trocáveis.\n"
        "- Amostra curta: poucas dezenas de pontos por horizonte; veja os ICs.",
    ]
    return "\n\n".join(sections) + "\n"


def write_report(text: str, path: Path) -> Path:
    """Grava o relatório em disco.

    Parameters
    ----------
    text : str
        Conteúdo Markdown.
    path : Path
        Arquivo de destino.

    Returns
    -------
    Path
        Caminho gravado.

    Examples
    --------
    >>> write_report("# oi", Path("reports/relatorio_final.md"))  # doctest: +SKIP
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path
