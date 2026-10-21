"""Registro do backtest no MLflow: 1 run pai (config, dados, artefatos) + 1 run por modelo."""

import logging
import subprocess  # nosec B404 - usado só para `git rev-parse`
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import mlflow
import polars as pl

from config.settings import Settings

logger = logging.getLogger(__name__)


def get_git_sha() -> str:
    """Retorna o SHA do commit atual ou ``"unknown"`` se não for um repositório git.

    Returns
    -------
    str
        Hash do ``HEAD``.

    Examples
    --------
    >>> len(get_git_sha()) in (7, 40)  # doctest: +SKIP
    True
    """
    try:
        result = subprocess.run(  # nosec B603 B607 - comando fixo, sem entrada do usuário
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True, timeout=10
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    return result.stdout.strip() or "unknown"


def flatten_params(settings: Settings) -> dict[str, Any]:
    """Achata os parâmetros que definem o experimento para ``mlflow.log_params``.

    Parameters
    ----------
    settings : Settings
        Configuração validada.

    Returns
    -------
    dict[str, Any]
        Parâmetros de backtest, LightGBM, statsforecast e semente.

    Examples
    --------
    >>> flatten_params(settings)["backtest.horizons"]  # doctest: +SKIP
    '[1, 2, 3, 6, 12]'
    """
    flat: dict[str, Any] = {"random_seed": settings.random_seed, "version": settings.version}
    for prefix, section in {
        "backtest": settings.backtest,
        "lightgbm": settings.model_params.lightgbm,
        "statsforecast": settings.model_params.statsforecast,
        "focus": settings.focus,
    }.items():
        for key, value in section.model_dump(mode="json").items():
            flat[f"{prefix}.{key}"] = value
    flat["series"] = ",".join(
        f"{s.name}:{s.sgs_code}:lag{s.release_lag_days}" for s in settings.series
    )
    return flat


def log_backtest_run(
    settings: Settings,
    metrics: pl.DataFrame,
    data_hashes: Mapping[str, str],
    artifacts: Sequence[Path],
    tracking_uri: str | None = None,
) -> str:
    """Registra o backtest no MLflow.

    O run pai guarda parâmetros, SHA do git, hashes dos dados e artefatos. Cada modelo
    ganha um run filho com ``mae_h{h}`` e ``rmse_h{h}``.

    Parameters
    ----------
    settings : Settings
        Configuração validada.
    metrics : pl.DataFrame
        Saída de ``compute_metrics`` (``model``, ``horizon``, ``mae``, ``rmse``).
    data_hashes : Mapping[str, str]
        SHA-256 dos insumos (ledger, supervisionada, Focus).
    artifacts : Sequence[Path]
        Arquivos a anexar ao run pai (ignora os inexistentes).
    tracking_uri : str | None, optional
        Sobrescreve ``settings.mlflow.tracking_uri``.

    Returns
    -------
    str
        ``run_id`` do run pai.

    Examples
    --------
    >>> log_backtest_run(settings, metrics, {"ledger": "abc"}, [])  # doctest: +SKIP
    """
    uri = tracking_uri or settings.mlflow.tracking_uri
    if uri.startswith("sqlite:///"):  # o SQLite não cria o diretório pai sozinho
        Path(uri.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
    mlflow.set_tracking_uri(uri)
    mlflow.set_experiment(settings.mlflow.experiment_name)
    run_id = ""
    with mlflow.start_run(run_name="walk_forward") as parent:
        mlflow.set_tag("git_sha", get_git_sha())
        mlflow.log_params(flatten_params(settings))
        mlflow.log_params({f"data_sha256.{k}": v[:16] for k, v in data_hashes.items()})
        for model in metrics["model"].unique(maintain_order=True).to_list():
            _log_model_run(model, metrics.filter(pl.col("model") == model))
        for path in artifacts:
            if path.is_file():
                mlflow.log_artifact(str(path))
        run_id = parent.info.run_id
        logger.info("Run MLflow registrado: %s", run_id)
    return run_id


def _log_model_run(model: str, metrics: pl.DataFrame) -> None:
    """Registra um run filho com as métricas de um modelo por horizonte."""
    with mlflow.start_run(run_name=model, nested=True):
        mlflow.set_tag("model", model)
        for row in metrics.iter_rows(named=True):
            mlflow.log_metric(f"mae_h{row['horizon']}", row["mae"])
            mlflow.log_metric(f"rmse_h{row['horizon']}", row["rmse"])
