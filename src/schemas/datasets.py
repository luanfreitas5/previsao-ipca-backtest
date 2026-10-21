"""Schemas pandera dos datasets de cada camada, com validação que falha cedo."""

import pandera.errors as pandera_errors
import pandera.polars as pa
import polars as pl

from exceptions.data import DataValidationError

SGS_SILVER_SCHEMA = pa.DataFrameSchema(
    {
        "series": pa.Column(pl.String, nullable=False),
        "date": pa.Column(pl.Date, nullable=False),
        "value": pa.Column(pl.Float64, nullable=False),
    },
    unique=["series", "date"],
    strict=True,
)

FOCUS_SILVER_SCHEMA = pa.DataFrameSchema(
    {
        "survey_date": pa.Column(pl.Date, nullable=False),
        "reference_month": pa.Column(pl.Date, nullable=False),
        "median": pa.Column(pl.Float64, nullable=False),
        "mean": pa.Column(pl.Float64, nullable=True),
        "std": pa.Column(pl.Float64, nullable=True),
        "min": pa.Column(pl.Float64, nullable=True),
        "max": pa.Column(pl.Float64, nullable=True),
        "n_respondents": pa.Column(pl.Int64, pa.Check.ge(0), nullable=True),
    },
    unique=["survey_date", "reference_month"],
    strict=True,
)

LEDGER_SCHEMA = pa.DataFrameSchema(
    {
        "series": pa.Column(pl.String, nullable=False),
        "period": pa.Column(pl.Date, nullable=False),
        "value": pa.Column(pl.Float64, nullable=False),
        "available_at": pa.Column(pl.Date, nullable=False),
    },
    unique=["series", "period"],
    strict=True,
)

FORECASTS_SCHEMA = pa.DataFrameSchema(
    {
        "model": pa.Column(pl.String, nullable=False),
        "origin": pa.Column(pl.Date, nullable=False),
        "horizon": pa.Column(pl.Int64, pa.Check.ge(1), nullable=False),
        "target_period": pa.Column(pl.Date, nullable=False),
        "target_available_at": pa.Column(pl.Date, nullable=False),
        "y_true": pa.Column(pl.Float64, nullable=False),
        "y_pred": pa.Column(pl.Float64, nullable=True),
    },
    unique=["model", "origin", "horizon"],
    strict=False,  # colunas de intervalo conformal são adicionadas depois
)


def validate_dataframe(df: pl.DataFrame, schema: pa.DataFrameSchema, name: str) -> pl.DataFrame:
    """Valida um DataFrame contra um schema pandera.

    Parameters
    ----------
    df : pl.DataFrame
        Dados a validar.
    schema : pa.DataFrameSchema
        Contrato esperado.
    name : str
        Nome legível do dataset (usado na mensagem de erro).

    Returns
    -------
    pl.DataFrame
        O próprio ``df`` quando válido.

    Raises
    ------
    DataValidationError
        Se o contrato for violado.

    Examples
    --------
    >>> validate_dataframe(sgs_df, SGS_SILVER_SCHEMA, "sgs_silver")  # doctest: +SKIP
    """
    try:
        return schema.validate(df)
    except (pandera_errors.SchemaError, pandera_errors.SchemaErrors) as error:
        raise DataValidationError(f"Contrato de dados violado em '{name}': {error}") from error


def validate_ledger(ledger: pl.DataFrame) -> pl.DataFrame:
    """Valida o ledger point-in-time: schema, disponibilidade e meses contíguos.

    Regras adicionais ao schema: ``available_at`` nunca anterior ao fim do período
    e cada série tem meses consecutivos (sem buracos), pois os lags dependem disso.

    Parameters
    ----------
    ledger : pl.DataFrame
        Colunas ``series``, ``period``, ``value``, ``available_at``.

    Returns
    -------
    pl.DataFrame
        O próprio ``ledger`` quando válido.

    Raises
    ------
    DataValidationError
        Se alguma regra for violada.

    Examples
    --------
    >>> validate_ledger(ledger)  # doctest: +SKIP
    """
    validate_dataframe(ledger, LEDGER_SCHEMA, "ledger")
    early = ledger.filter(pl.col("available_at") < pl.col("period").dt.month_end())
    if not early.is_empty():
        raise DataValidationError(
            f"{early.height} observações com available_at anterior ao fim do período"
        )
    month_index = pl.col("period").dt.year().cast(pl.Int64) * 12 + pl.col("period").dt.month()
    gaps = (
        ledger.sort("series", "period")
        .with_columns(month_index.diff().over("series").alias("_gap"))
        .filter(pl.col("_gap") > 1)
    )
    if not gaps.is_empty():
        names = gaps["series"].unique().to_list()
        raise DataValidationError(f"Séries com meses faltantes no ledger: {names}")
    return ledger
