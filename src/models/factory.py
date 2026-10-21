"""Fábrica de modelos a partir da configuração."""

from config.settings import Settings
from exceptions.base import ConfigurationError
from models.base import Forecaster
from models.focus import FocusBaseline
from models.lightgbm_model import LightGBMDirect
from models.naive import NaiveLast, SeasonalNaive
from models.statistical import StatsForecastModel


def build_models(settings: Settings, feature_columns: list[str]) -> list[Forecaster]:
    """Cria os modelos listados em ``backtest.models`` e adiciona o baseline Focus.

    Parameters
    ----------
    settings : Settings
        Configuração validada.
    feature_columns : list[str]
        Colunas de features para o LightGBM.

    Returns
    -------
    list[Forecaster]
        Modelos configurados mais o ``FocusBaseline`` ao final.

    Raises
    ------
    ConfigurationError
        Se um nome de modelo for desconhecido.

    Examples
    --------
    >>> [m.name for m in build_models(settings, cols)]  # doctest: +SKIP
    ['naive_last', 'naive_seasonal', 'arima', 'ets', 'lightgbm', 'focus']
    """
    season = settings.model_params.statsforecast.season_length
    builders = {
        "naive_last": NaiveLast,
        "naive_seasonal": SeasonalNaive,
        "arima": lambda: StatsForecastModel("arima", lambda: _build_arima(season)),
        "ets": lambda: StatsForecastModel("ets", lambda: _build_ets(season)),
        "lightgbm": lambda: LightGBMDirect(
            settings.model_params.lightgbm, feature_columns, settings.random_seed
        ),
    }
    unknown = [name for name in settings.backtest.models if name not in builders]
    if unknown:
        raise ConfigurationError(f"Modelos desconhecidos: {unknown}")
    return [builders[name]() for name in settings.backtest.models] + [FocusBaseline()]


def _build_arima(season_length: int):
    """AutoARIMA sazonal (importação tardia: statsforecast compila com numba)."""
    from statsforecast.models import AutoARIMA

    return AutoARIMA(season_length=season_length, alias="arima")


def _build_ets(season_length: int):
    """AutoETS (seleção automática de erro, tendência e sazonalidade)."""
    from statsforecast.models import AutoETS

    return AutoETS(season_length=season_length, model="ZZZ", alias="ets")
