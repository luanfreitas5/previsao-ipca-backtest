"""Baselines ingênuos: último valor e sazonal ingênuo."""

import math
from datetime import date

from models.base import ForecastContext, Forecaster
from utils.dates import add_months, months_between


class NaiveLast(Forecaster):
    """Repete o último IPCA divulgado para todos os horizontes.

    Examples
    --------
    >>> NaiveLast().name
    'naive_last'
    """

    name = "naive_last"

    def forecast(self, context: ForecastContext) -> dict[int, float]:
        """Prevê o último valor divulgado, independente do horizonte.

        Parameters
        ----------
        context : ForecastContext
            Conjunto de informação da origem.

        Returns
        -------
        dict[int, float]
            Mesmo valor para todos os horizontes.
        """
        history = context.ipca_history.sort("period")
        last_value = float(history["value"][-1]) if history.height else math.nan
        return dict.fromkeys(context.horizons, last_value)


class SeasonalNaive(Forecaster):
    """Usa o IPCA do mesmo mês de um ano anterior que já foi divulgado.

    Para o mês-alvo ``T``, escolhe ``T - 12k`` com o menor ``k >= 1`` tal que o
    período já esteja no histórico divulgado na origem.

    Examples
    --------
    >>> SeasonalNaive().name
    'naive_seasonal'
    """

    name = "naive_seasonal"

    def forecast(self, context: ForecastContext) -> dict[int, float]:
        """Prevê o valor do mesmo mês do ano anterior (ou o mais recente disponível).

        Parameters
        ----------
        context : ForecastContext
            Conjunto de informação da origem.

        Returns
        -------
        dict[int, float]
            Previsão por horizonte; ``nan`` se o histórico não alcançar o período.
        """
        values: dict[date, float] = dict(
            zip(
                context.ipca_history["period"].to_list(),
                context.ipca_history["value"].to_list(),
                strict=True,
            )
        )
        last = context.last_period
        result: dict[int, float] = {}
        for horizon in context.horizons:
            target = context.target_period(horizon)
            years_back = max(1, math.ceil(months_between(last, target) / 12))
            result[horizon] = values.get(add_months(target, -12 * years_back), math.nan)
        return result
