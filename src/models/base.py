"""Interface comum dos modelos e o conjunto de informação disponível em cada origem."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date

import polars as pl

from utils.dates import add_months, month_start


@dataclass(frozen=True)
class ForecastContext:
    """Tudo o que um modelo pode saber na data de origem (e nada além).

    Attributes
    ----------
    origin : date
        Data de origem da previsão (fim de mês).
    horizons : tuple[int, ...]
        Horizontes solicitados, em meses à frente do mês da origem.
    ipca_history : pl.DataFrame
        IPCA divulgado até a origem (``period``, ``value``, ``available_at``).
    train : pl.DataFrame
        Linhas supervisionadas cujo alvo já era público na origem.
    test : pl.DataFrame
        Linhas supervisionadas da própria origem (features; ``y_true`` NÃO deve ser usado).
    """

    origin: date
    horizons: tuple[int, ...]
    ipca_history: pl.DataFrame
    train: pl.DataFrame
    test: pl.DataFrame

    @property
    def last_period(self) -> date:
        """Mês do último IPCA já divulgado na origem."""
        return self.ipca_history["period"].max()  # type: ignore[return-value]

    def target_period(self, horizon: int) -> date:
        """Mês-alvo (primeiro dia) para um horizonte: mês da origem + ``horizon``."""
        return add_months(month_start(self.origin), horizon)


class Forecaster(ABC):
    """Interface de um modelo de previsão pontual do IPCA mensal.

    Attributes
    ----------
    name : str
        Identificador usado nas tabelas, figuras e no MLflow.
    """

    name: str

    @abstractmethod
    def forecast(self, context: ForecastContext) -> dict[int, float]:
        """Prevê o IPCA de cada horizonte usando somente o contexto da origem.

        Parameters
        ----------
        context : ForecastContext
            Conjunto de informação disponível na origem.

        Returns
        -------
        dict[int, float]
            Previsão por horizonte (``nan`` quando o modelo não consegue prever).
        """
