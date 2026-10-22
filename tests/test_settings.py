"""Testes de carregamento e validação das configurações."""

import shutil
from pathlib import Path

import pytest

from config.paths import CONFIG_DIR
from config.settings import Settings, load_settings, read_yaml
from exceptions.base import ConfigurationError


@pytest.mark.smoke
def test_real_configs_are_valid(settings: Settings):
    assert settings.series_names[0] == "ipca"
    assert settings.backtest.horizons == sorted(settings.backtest.horizons)
    assert settings.paths.data_bronze.name == "bronze"


def test_unknown_key_is_rejected(tmp_path: Path):
    config_dir = tmp_path / "configs"
    shutil.copytree(CONFIG_DIR, config_dir)
    path = config_dir / "config.yaml"
    path.write_text(path.read_text(encoding="utf-8") + "\nchave_inexistente: 1\n", encoding="utf-8")
    with pytest.raises(ConfigurationError):
        load_settings(config_dir, tmp_path)


def test_invalid_horizon_is_rejected(tmp_path: Path):
    config_dir = tmp_path / "configs"
    shutil.copytree(CONFIG_DIR, config_dir)
    path = config_dir / "config.yaml"
    path.write_text(
        path.read_text(encoding="utf-8").replace("[1, 2, 3, 6, 12]", "[0, 1]"), encoding="utf-8"
    )
    with pytest.raises(ConfigurationError):
        load_settings(config_dir, tmp_path)


def test_missing_file_raises(tmp_path: Path):
    with pytest.raises(ConfigurationError):
        read_yaml(tmp_path / "nao_existe.yaml")


def test_env_overrides_tracking_uri(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MLFLOW_TRACKING_URI", "sqlite:///outro.db")
    assert load_settings().mlflow.tracking_uri == "sqlite:///outro.db"
