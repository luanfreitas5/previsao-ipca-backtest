"""Testes da análise consolidada, do relatório em Markdown e das figuras."""

from pathlib import Path

import polars as pl
import pytest

from config.settings import Settings
from helpers import make_forecasts
from reporting.analysis import analyze_forecasts
from reporting.report import (
    render_report,
    summarize_vs_reference,
    to_markdown_table,
    write_report,
)
from visualization.plots import (
    plot_conformal_coverage,
    plot_forecasts_vs_actual,
    plot_rmse_by_horizon,
)
from visualization.theme import color_for, save_figure


@pytest.fixture(scope="module")
def fast_settings(settings: Settings) -> Settings:
    return settings.model_copy(
        update={"report": settings.report.model_copy(update={"n_bootstrap": 100})}
    )


@pytest.fixture(scope="module")
def analysis(fast_settings: Settings):
    forecasts = make_forecasts(("naive_last", "arima", "focus"), (1, 3))
    return analyze_forecasts(forecasts, fast_settings)


def test_analysis_picks_most_accurate_non_reference_model(analysis):
    assert analysis.best_model == "naive_last"  # menor ruído sintético
    assert "lower" in analysis.forecasts.columns
    assert analysis.worst.height == 10


def test_analysis_tables_are_consistent(analysis):
    assert set(analysis.metrics["model"]) == {"naive_last", "arima", "focus"}
    assert set(analysis.dm_squared["model"]) == {"naive_last", "arima"}
    assert analysis.coverage["coverage"].is_between(0, 1).all()


def test_report_mentions_where_models_lose_to_focus(analysis, fast_settings: Settings):
    text = render_report(analysis, fast_settings, ["rmse_por_horizonte"])
    assert "Onde os modelos perdem para o Focus" in text
    assert "![rmse_por_horizonte](figures/rmse_por_horizonte.png)" in text
    assert "Limitações" in text
    lines = summarize_vs_reference(analysis, "focus")
    assert len(lines) == 4
    assert all("supera" in line for line in lines)  # o Focus sintético é o pior de propósito


def test_summary_flags_losses(analysis):
    flipped = analysis.__class__(
        **{
            **analysis.__dict__,
            "metrics": analysis.metrics.with_columns(pl.col("rmse_ratio") * 0 + 2.0),
        }
    )
    assert all("perde" in line for line in summarize_vs_reference(flipped, "focus"))


def test_markdown_table_formats_floats():
    table = to_markdown_table(pl.DataFrame({"a": [1.23456], "b": ["x"]}), digits=2)
    assert table.splitlines() == ["| a | b |", "| --- | --- |", "| 1.23 | x |"]


def test_write_report_creates_parent_directories(tmp_path: Path):
    path = write_report("# oi\n", tmp_path / "a" / "b" / "relatorio.md")
    assert path.read_text(encoding="utf-8") == "# oi\n"


def test_figures_are_saved_as_png_and_svg(analysis, tmp_path: Path):
    figures = {
        "rmse": plot_rmse_by_horizon(analysis.metrics),
        "serie": plot_forecasts_vs_actual(analysis.forecasts, 1, ["focus", "naive_last"]),
        "cobertura": plot_conformal_coverage(analysis.coverage, 0.9),
    }
    for name, fig in figures.items():
        paths = save_figure(fig, tmp_path, name)
        assert [p.suffix for p in paths] == [".png", ".svg"]
        assert all(p.stat().st_size > 0 for p in paths)


def test_color_for_unknown_model_falls_back():
    assert color_for("focus") != color_for("modelo-desconhecido")
