"""Exceções base do projeto."""


class IpcaBacktestError(Exception):
    """Exceção raiz: todas as exceções do projeto herdam desta classe."""


class ConfigurationError(IpcaBacktestError):
    """Configuração ausente, malformada ou inconsistente."""
