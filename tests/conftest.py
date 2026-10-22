"""Fixtures compartilhadas."""

import polars as pl
import pytest

from config.settings import Settings, load_settings
from helpers import make_ledger, make_supervised


@pytest.fixture(scope="session")
def settings() -> Settings:
    """Configuração real do projeto (valida os YAML versionados)."""
    return load_settings()


@pytest.fixture(scope="session")
def ledger() -> pl.DataFrame:
    """Ledger sintético de 72 meses."""
    return make_ledger()


@pytest.fixture(scope="session")
def supervised(ledger: pl.DataFrame) -> pl.DataFrame:
    """Tabela supervisionada sintética com horizontes 1 e 3."""
    return make_supervised(ledger)
