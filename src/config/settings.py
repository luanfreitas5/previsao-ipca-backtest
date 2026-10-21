"""Carrega e valida as configurações YAML com Pydantic (falha cedo, com erro tipado)."""

from datetime import date
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from config.paths import CONFIG_DIR, ROOT
from exceptions.base import ConfigurationError

ModelName = Literal["naive_last", "naive_seasonal", "arima", "ets", "lightgbm"]


class _Strict(BaseModel):
    """Base com ``extra="forbid"``: chaves desconhecidas no YAML são erro."""

    # protected_namespaces vazio: o campo `model_params` começa com "model_".
    model_config = ConfigDict(extra="forbid", protected_namespaces=())


class DataConfig(_Strict):
    """Parâmetros de coleta das APIs do BCB."""

    start_date: date
    sgs_base_url: str
    olinda_url: str
    request_timeout_s: float = Field(gt=0)
    max_retries: int = Field(ge=0)
    backoff_s: float = Field(ge=0)
    chunk_years: int = Field(ge=1, le=10)
    focus_page_size: int = Field(ge=1)


class FocusConfig(_Strict):
    """Parâmetros de uso do Boletim Focus como baseline."""

    indicator: str
    base_calculo: int = Field(ge=0, le=1)
    publication_lag_days: int = Field(ge=0)
    max_staleness_days: int = Field(ge=0)


class SeriesConfig(_Strict):
    """Definição de uma série SGS e de sua regra de disponibilidade."""

    name: str
    sgs_code: int = Field(gt=0)
    frequency: Literal["daily", "monthly"]
    aggregation: Literal["last", "mean", "sum"]
    transform: Literal["level", "pct_change", "diff"]
    release_lag_days: int = Field(ge=0)
    description: str


class BacktestConfig(_Strict):
    """Parâmetros do backtest walk-forward."""

    first_origin: date
    last_origin: date | None = None
    horizons: list[int]
    n_lags: int = Field(ge=12)
    alpha: float = Field(gt=0, lt=1)
    min_calibration: int = Field(ge=5)
    models: list[ModelName]

    @field_validator("horizons")
    @classmethod
    def _validate_horizons(cls, value: list[int]) -> list[int]:
        """Garante horizontes positivos, únicos e ordenados."""
        if not value or any(h < 1 for h in value) or len(set(value)) != len(value):
            raise ValueError("horizons deve conter inteiros positivos e únicos")
        return sorted(value)


class SliceConfig(_Strict):
    """Subperíodo (pelo mês-alvo) para avaliação por fatias."""

    name: str
    start: date
    end: date


class ReportConfig(_Strict):
    """Parâmetros do relatório final."""

    reference_model: str
    n_bootstrap: int = Field(ge=100)
    worst_errors_k: int = Field(ge=1)
    slices: list[SliceConfig]


class MlflowConfig(_Strict):
    """Parâmetros do MLflow."""

    experiment_name: str
    tracking_uri: str


class LightGBMParams(_Strict):
    """Hiperparâmetros do LightGBM (API nativa)."""

    num_boost_round: int = Field(gt=0)
    learning_rate: float = Field(gt=0, le=1)
    num_leaves: int = Field(gt=1)
    min_data_in_leaf: int = Field(ge=1)
    feature_fraction: float = Field(gt=0, le=1)
    bagging_fraction: float = Field(gt=0, le=1)
    bagging_freq: int = Field(ge=0)
    lambda_l2: float = Field(ge=0)
    min_train_rows: int = Field(ge=10)


class StatsForecastParams(_Strict):
    """Parâmetros dos modelos estatísticos."""

    season_length: int = Field(ge=1)


class ModelParams(_Strict):
    """Hiperparâmetros de todos os modelos."""

    statsforecast: StatsForecastParams
    lightgbm: LightGBMParams


class LoggingConfig(_Strict):
    """Configuração de logging."""

    level: str
    file_format: str


class PathsConfig(_Strict):
    """Caminhos absolutos (já resolvidos a partir da raiz do projeto)."""

    data_bronze: Path
    data_silver: Path
    data_gold: Path
    reports: Path
    figures: Path
    tables: Path
    logs: Path


class EnvConfig(BaseSettings):
    """Variáveis de ambiente opcionais (``.env``)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    mlflow_tracking_uri: str | None = None


class Settings(_Strict):
    """Configuração global validada do projeto."""

    version: str
    random_seed: int
    data: DataConfig
    focus: FocusConfig
    backtest: BacktestConfig
    report: ReportConfig
    mlflow: MlflowConfig
    series: list[SeriesConfig]
    model_params: ModelParams
    logging: LoggingConfig
    paths: PathsConfig

    @property
    def series_names(self) -> list[str]:
        """Nomes das séries na ordem do catálogo."""
        return [s.name for s in self.series]


def read_yaml(path: Path) -> dict[str, Any]:
    """Lê um arquivo YAML e devolve um dicionário.

    Parameters
    ----------
    path : Path
        Caminho do arquivo.

    Returns
    -------
    dict[str, Any]
        Conteúdo do YAML.

    Raises
    ------
    ConfigurationError
        Se o arquivo não existir ou não contiver um mapeamento.
    """
    if not path.is_file():
        raise ConfigurationError(f"Arquivo de configuração não encontrado: {path}")
    content = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(content, dict):
        raise ConfigurationError(f"Configuração inválida (esperado mapeamento): {path}")
    return content


def load_settings(config_dir: Path = CONFIG_DIR, root: Path = ROOT) -> Settings:
    """Carrega ``configs/*.yaml`` + ``.env`` e valida tudo de uma vez.

    Parameters
    ----------
    config_dir : Path, optional
        Diretório com os YAML, by default ``configs/`` do projeto.
    root : Path, optional
        Raiz para resolver os caminhos de ``paths.yaml``.

    Returns
    -------
    Settings
        Configuração validada.

    Raises
    ------
    ConfigurationError
        Se algum arquivo faltar ou a validação falhar.

    Examples
    --------
    >>> settings = load_settings()  # doctest: +SKIP
    >>> settings.backtest.horizons  # doctest: +SKIP
    [1, 2, 3, 6, 12]
    """
    general = read_yaml(config_dir / "config.yaml")
    raw_paths = read_yaml(config_dir / "paths.yaml")
    env = EnvConfig()
    if env.mlflow_tracking_uri:
        general["mlflow"]["tracking_uri"] = env.mlflow_tracking_uri
    try:
        return Settings.model_validate(
            general
            | {
                "series": read_yaml(config_dir / "series.yaml")["series"],
                "model_params": read_yaml(config_dir / "model_params.yaml"),
                "logging": read_yaml(config_dir / "logging.yaml"),
                "paths": {key: root / value for key, value in raw_paths.items()},
            }
        )
    except (ValidationError, KeyError) as error:
        raise ConfigurationError(f"Configuração inválida: {error}") from error
