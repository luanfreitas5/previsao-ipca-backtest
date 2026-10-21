"""Configuração de logging: console (rich) e arquivo diário."""

import logging
from datetime import date
from pathlib import Path

from rich.logging import RichHandler


def configure_logging(
    level: str = "INFO",
    log_dir: Path | None = None,
    file_format: str = "%(asctime)s \t %(levelname)s \t %(name)s \t %(message)s",
) -> None:
    """Configura o logging raiz com handler rich e, opcionalmente, arquivo diário.

    Parameters
    ----------
    level : str, optional
        Nível de log (``DEBUG``, ``INFO`` ...), by default ``"INFO"``.
    log_dir : Path | None, optional
        Diretório dos logs; cria ``log_YYYY-MM-DD.log``. ``None`` desativa o arquivo.
    file_format : str, optional
        Formato das linhas do arquivo.

    Examples
    --------
    >>> configure_logging("INFO")
    """
    handlers: list[logging.Handler] = [RichHandler(rich_tracebacks=True, show_path=False)]
    if log_dir is not None:
        log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(
            log_dir / f"log_{date.today():%Y-%m-%d}.log", encoding="utf-8"
        )
        file_handler.setFormatter(logging.Formatter(file_format))
        handlers.append(file_handler)
    logging.basicConfig(level=level.upper(), format="%(message)s", handlers=handlers, force=True)
