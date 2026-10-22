"""Testes de infraestrutura: hashing, I/O, logging, semente, tracker e CLI."""

import logging
import random
from pathlib import Path

import mlflow
import numpy as np
import polars as pl
import pytest

from config.environment import seed_everything
from config.logging_setup import configure_logging
from config.settings import Settings
from data.reader import read_json, read_parquet
from data.writer import write_json_atomic, write_parquet
from exceptions.base import IpcaBacktestError
from exceptions.data import DataValidationError
from experiment.tracker import flatten_params, get_git_sha, log_backtest_run
from main import build_parser, main
from utils.hashing import hash_bytes, hash_file


def test_hash_file_matches_hash_bytes(tmp_path: Path):
    path = tmp_path / "a.bin"
    path.write_bytes(b"ipca")
    assert hash_file(path) == hash_bytes(b"ipca")


def test_parquet_and_json_roundtrip(tmp_path: Path):
    df = pl.DataFrame({"a": [1, 2]})
    assert read_parquet(write_parquet(df, tmp_path / "x" / "d.parquet")).equals(df)
    assert read_json(write_json_atomic({"k": "ç"}, tmp_path / "m.json")) == {"k": "ç"}


def test_missing_and_invalid_files_raise(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        read_parquet(tmp_path / "nao_existe.parquet")
    with pytest.raises(FileNotFoundError):
        read_json(tmp_path / "nao_existe.json")
    bad = tmp_path / "ruim.json"
    bad.write_text("{", encoding="utf-8")
    with pytest.raises(DataValidationError):
        read_json(bad)


def test_seed_everything_makes_randomness_reproducible():
    seed_everything(7)
    first = (random.random(), np.random.rand())  # noqa: NPY002
    seed_everything(7)
    assert (random.random(), np.random.rand()) == first  # noqa: NPY002


def test_configure_logging_writes_daily_file(tmp_path: Path):
    root = logging.getLogger()
    saved, level = root.handlers[:], root.level
    try:
        configure_logging("INFO", tmp_path / "logs")
        logging.getLogger("teste").info("mensagem de teste")
        for handler in root.handlers:
            handler.flush()
        assert list((tmp_path / "logs").glob("log_*.log"))
    finally:
        for handler in root.handlers[:]:
            root.removeHandler(handler)
            handler.close()
        root.handlers = saved
        root.setLevel(level)


def test_get_git_sha_returns_string():
    assert isinstance(get_git_sha(), str)


def test_flatten_params_contains_backtest_and_series(settings: Settings):
    flat = flatten_params(settings)
    assert "backtest.horizons" in flat
    assert flat["series"].startswith("ipca:433:lag10")


def test_log_backtest_run_creates_parent_and_child_runs(
    settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(tmp_path)
    metrics = pl.DataFrame(
        {"model": ["arima", "focus"], "horizon": [1, 1], "mae": [0.2, 0.1], "rmse": [0.3, 0.2]}
    )
    artifact = tmp_path / "tabela.csv"
    metrics.write_csv(artifact)
    uri = f"sqlite:///{(tmp_path / 'mlflow.db').as_posix()}"
    run_id = log_backtest_run(settings, metrics, {"ledger": "a" * 64}, [artifact], tracking_uri=uri)
    run = mlflow.get_run(run_id)
    assert "git_sha" in run.data.tags
    assert run.data.params["data_sha256.ledger"] == "a" * 16
    children = mlflow.search_runs(
        experiment_ids=[run.info.experiment_id],
        filter_string=f"tags.mlflow.parentRunId = '{run_id}'",
        output_format="list",
    )
    assert {c.data.tags["model"] for c in children} == {"arima", "focus"}


@pytest.mark.smoke
def test_cli_parser_accepts_known_stages():
    assert build_parser().parse_args(["backtest", "--force"]).force is True
    with pytest.raises(SystemExit):
        build_parser().parse_args(["estagio-inexistente"])


def test_main_returns_error_code_on_bad_config(tmp_path: Path):
    assert main(["silver", "--config-dir", str(tmp_path)]) == 1


def test_project_errors_share_a_common_root():
    assert issubclass(DataValidationError, IpcaBacktestError)
