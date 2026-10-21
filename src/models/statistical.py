"""ARIMA e ETS automáticos via statsforecast."""

import math
from collections.abc import Callable
from typing import Any

import pandas as pd

from models.base import ForecastContext, Forecaster
from utils.dates import months_between


class StatsForecastModel(Forecaster):
    """Ajusta um modelo do statsforecast na janela expansiva e prevê todos os passos.

    Como o IPCA do mês da origem ainda não foi divulgado, o horizonte ``h`` do
    projeto corresponde a ``steps = h + defasagem`` passos à frente do último dado.

    Parameters
    ----------
    name : str
        Identificador (``"arima"`` ou ``"ets"``).
    model_factory : Callable[[], Any]
        Função que devolve o modelo do statsforecast já com ``alias`` igual a ``name``.

    Examples
    --------
    >>> from statsforecast.models import AutoARIMA
    >>> model = StatsForecastModel("arima", lambda: AutoARIMA(season_length=12, alias="arima"))
    """

    def __init__(self, name: str, model_factory: Callable[[], Any]) -> None:
        self.name = name
        self._model_factory = model_factory

    def forecast(self, context: ForecastContext) -> dict[int, float]:
        """Ajusta o modelo no IPCA divulgado até a origem e prevê cada horizonte.

        Parameters
        ----------
        context : ForecastContext
            Conjunto de informação da origem.

        Returns
        -------
        dict[int, float]
            Previsão por horizonte (``nan`` se o passo exceder o horizonte ajustado).
        """
        from statsforecast import StatsForecast

        history = context.ipca_history.sort("period")
        frame = pd.DataFrame(
            {
                "unique_id": "ipca",
                "ds": pd.to_datetime(history["period"].to_list()),
                "y": history["value"].to_numpy(),
            }
        )
        steps = {
            h: months_between(context.last_period, context.target_period(h))
            for h in context.horizons
        }
        output: Any = StatsForecast(models=[self._model_factory()], freq="MS", n_jobs=1).forecast(
            df=frame, h=max(steps.values())
        )
        if "unique_id" not in output.columns:  # statsforecast 1.x usa unique_id como índice
            output = output.reset_index()
        path = output.sort_values("ds")[self.name].to_numpy()
        return {
            h: float(path[s - 1]) if 1 <= s <= len(path) else math.nan for h, s in steps.items()
        }
