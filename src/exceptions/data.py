"""Exceções relacionadas a dados."""

from exceptions.base import IpcaBacktestError


class IngestionError(IpcaBacktestError):
    """Falha ao baixar ou persistir dados de uma fonte externa."""


class DataValidationError(IpcaBacktestError):
    """Dados violam o contrato esperado (schema, contiguidade, tipos)."""


class LeakageError(IpcaBacktestError):
    """Informação posterior à data de origem foi detectada no conjunto de informação."""
