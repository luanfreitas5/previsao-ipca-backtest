"""Modelos de previsão do IPCA, todos sob a interface ``Forecaster``.

Módulos
-------
base
    ``Forecaster`` (interface) e ``ForecastContext`` (conjunto de informação da origem).
naive
    ``NaiveLast`` e ``SeasonalNaive``.
statistical
    ``StatsForecastModel`` (AutoARIMA e AutoETS via statsforecast).
lightgbm_model
    ``LightGBMDirect``: um LightGBM por horizonte, com lags point-in-time.
focus
    ``FocusBaseline``: mediana do Boletim Focus vigente na origem.
factory
    ``build_models`` cria os modelos a partir da configuração.
"""
