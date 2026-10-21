"""Orquestração do pipeline: ``python src/main.py <estágio> [opções]``."""

import argparse
import logging
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

from config.environment import seed_everything
from config.logging_setup import configure_logging
from config.paths import CONFIG_DIR
from config.settings import Settings, load_settings
from exceptions.base import IpcaBacktestError
from pipelines.stages import run_backtest, run_gold, run_ingest, run_report, run_silver

logger = logging.getLogger(__name__)

STAGES: dict[str, Callable[[Settings], object]] = {
    "silver": run_silver,
    "gold": run_gold,
    "backtest": run_backtest,
    "report": run_report,
}


def build_parser() -> argparse.ArgumentParser:
    """Cria o parser de argumentos da CLI.

    Returns
    -------
    argparse.ArgumentParser
        Parser com os estágios ``ingest``, ``silver``, ``gold``, ``backtest``,
        ``report`` e ``all``.

    Examples
    --------
    >>> build_parser().parse_args(["silver"]).stage
    'silver'
    """
    parser = argparse.ArgumentParser(description="Previsão do IPCA com backtest walk-forward.")
    parser.add_argument("stage", choices=["ingest", *STAGES, "all"], help="Estágio a executar.")
    parser.add_argument("--config-dir", type=Path, default=CONFIG_DIR, help="Pasta dos YAML.")
    parser.add_argument("--force", action="store_true", help="Refaz o snapshot de hoje (ingest).")
    parser.add_argument("--log-level", default=None, help="Sobrescreve o nível de log do YAML.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Ponto de entrada da CLI.

    Parameters
    ----------
    argv : Sequence[str] | None, optional
        Argumentos (``None`` usa ``sys.argv``).

    Returns
    -------
    int
        Código de saída (0 = sucesso, 1 = erro do projeto).

    Examples
    --------
    >>> main(["backtest"])  # doctest: +SKIP
    0
    """
    args = build_parser().parse_args(argv)
    try:
        settings = load_settings(args.config_dir)
        configure_logging(
            args.log_level or settings.logging.level,
            settings.paths.logs,
            settings.logging.file_format,
        )
        seed_everything(settings.random_seed)
        if args.stage in ("ingest", "all"):
            run_ingest(settings, args.force)
        for name, stage in STAGES.items():
            if args.stage in (name, "all"):
                logger.info("Executando estágio: %s", name)
                stage(settings)
    except IpcaBacktestError:
        logger.exception("Falha no pipeline")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
