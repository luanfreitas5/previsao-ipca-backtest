"""Exceções customizadas do projeto.

Módulos
-------
base
    ``IpcaBacktestError`` (raiz) e ``ConfigurationError``.
data
    ``IngestionError``, ``DataValidationError`` e ``LeakageError``.
"""

from exceptions.base import ConfigurationError, IpcaBacktestError
from exceptions.data import DataValidationError, IngestionError, LeakageError

__all__ = [
    "ConfigurationError",
    "DataValidationError",
    "IngestionError",
    "IpcaBacktestError",
    "LeakageError",
]
