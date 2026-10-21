"""LightGBM direto (um modelo por horizonte) com lags point-in-time."""

import math

import lightgbm as lgb
import numpy as np
import polars as pl

from config.settings import LightGBMParams
from models.base import ForecastContext, Forecaster


class LightGBMDirect(Forecaster):
    """Treina um LightGBM por horizonte na janela expansiva e prevê a origem atual.

    O treino usa apenas ``context.train`` — linhas cujo alvo já havia sido divulgado
    na origem (garantido pelo motor de backtest). Nada de ``y_true`` da origem
    corrente é lido.

    Parameters
    ----------
    params : LightGBMParams
        Hiperparâmetros validados.
    feature_columns : list[str]
        Colunas de features, em ordem estável.
    seed : int
        Semente (determinismo: ``deterministic=True``, uma thread).

    Examples
    --------
    >>> model = LightGBMDirect(params, ["ipca_lag0"], seed=42)  # doctest: +SKIP
    """

    name = "lightgbm"

    def __init__(self, params: LightGBMParams, feature_columns: list[str], seed: int) -> None:
        self._params = params
        self._features = feature_columns
        self._seed = seed

    def forecast(self, context: ForecastContext) -> dict[int, float]:
        """Treina e prevê cada horizonte separadamente.

        Parameters
        ----------
        context : ForecastContext
            Conjunto de informação da origem.

        Returns
        -------
        dict[int, float]
            Previsão por horizonte (``nan`` se houver poucas linhas de treino).
        """
        return {h: self._forecast_horizon(context, h) for h in context.horizons}

    def _forecast_horizon(self, context: ForecastContext, horizon: int) -> float:
        """Treina o modelo do horizonte e prevê a linha de teste da origem."""
        train = context.train.filter(pl.col("horizon") == horizon).drop_nulls("y_true")
        test = context.test.filter(pl.col("horizon") == horizon)
        if train.height < self._params.min_train_rows or test.is_empty():
            return math.nan
        booster = lgb.train(
            self._build_params(),
            lgb.Dataset(self._to_matrix(train), label=train["y_true"].to_numpy()),
            num_boost_round=self._params.num_boost_round,
        )
        return float(np.asarray(booster.predict(self._to_matrix(test)))[0])

    def _to_matrix(self, frame: pl.DataFrame) -> np.ndarray:
        """Seleciona as features como matriz ``float64`` (nulos viram NaN)."""
        return frame.select(pl.col(c).cast(pl.Float64) for c in self._features).to_numpy()

    def _build_params(self) -> dict[str, float | int | str | bool]:
        """Converte os hiperparâmetros validados no dicionário da API nativa."""
        p = self._params
        return {
            "objective": "regression",
            "learning_rate": p.learning_rate,
            "num_leaves": p.num_leaves,
            "min_data_in_leaf": p.min_data_in_leaf,
            "feature_fraction": p.feature_fraction,
            "bagging_fraction": p.bagging_fraction,
            "bagging_freq": p.bagging_freq,
            "lambda_l2": p.lambda_l2,
            "seed": self._seed,
            "deterministic": True,
            "force_row_wise": True,
            "num_threads": 1,
            "verbosity": -1,
        }
