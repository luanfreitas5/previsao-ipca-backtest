"""Baseline de mercado: mediana do Boletim Focus vigente na origem."""

import math

from models.base import ForecastContext, Forecaster

FOCUS_MODEL_NAME = "focus"


class FocusBaseline(Forecaster):
    """Devolve a mediana do Focus para o mês-alvo, já filtrada por disponibilidade.

    A filtragem point-in-time (divulgação e defasagem máxima) é feita ao montar a
    tabela supervisionada; aqui apenas se lê ``focus_median``.

    Examples
    --------
    >>> FocusBaseline().name
    'focus'
    """

    name = FOCUS_MODEL_NAME

    def forecast(self, context: ForecastContext) -> dict[int, float]:
        """Lê a mediana do Focus de cada horizonte na origem.

        Parameters
        ----------
        context : ForecastContext
            Conjunto de informação da origem.

        Returns
        -------
        dict[int, float]
            Mediana do Focus por horizonte (``nan`` se não houver snapshot recente).
        """
        medians = dict(
            zip(
                context.test["horizon"].to_list(),
                context.test["focus_median"].to_list(),
                strict=True,
            )
        )
        return {h: _to_float(medians.get(h)) for h in context.horizons}


def _to_float(value: float | None) -> float:
    """Converte ``None`` em ``nan``."""
    return math.nan if value is None else float(value)
