"""Ingestão idempotente para a camada bronze (snapshots datados e imutáveis)."""

import json
import logging
from collections.abc import Callable
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from config.settings import Settings
from data.bcb_client import BcbClient
from data.reader import read_json
from data.writer import write_json_atomic
from exceptions.data import DataValidationError, IngestionError
from utils.hashing import hash_file

logger = logging.getLogger(__name__)

DATA_FILE = "data.json"
MANIFEST_FILE = "manifest.json"


def is_snapshot_valid(snapshot_dir: Path) -> bool:
    """Verifica se um snapshot existe e se o hash do dado confere com o manifesto.

    Parameters
    ----------
    snapshot_dir : Path
        Diretório ``bronze/<fonte>/<AAAA-MM-DD>``.

    Returns
    -------
    bool
        ``True`` se ``data.json`` e ``manifest.json`` existem e o SHA-256 confere.

    Examples
    --------
    >>> is_snapshot_valid(Path("data/bronze/sgs_ipca/2026-01-01"))  # doctest: +SKIP
    False
    """
    data_path = snapshot_dir / DATA_FILE
    manifest_path = snapshot_dir / MANIFEST_FILE
    if not (data_path.is_file() and manifest_path.is_file()):
        return False
    try:
        manifest = read_json(manifest_path)
    except (OSError, DataValidationError):
        return False
    return isinstance(manifest, dict) and manifest.get("sha256") == hash_file(data_path)


def ingest_source(
    source: str,
    fetch: Callable[[], list[Any]],
    bronze_dir: Path,
    snapshot_date: date,
    force: bool = False,
    metadata: dict[str, Any] | None = None,
) -> Path:
    """Baixa uma fonte e grava o snapshot do dia, a menos que já exista (cache local).

    Idempotente: se o snapshot do dia já existe e o hash confere, não faz requisição.
    Snapshots de dias anteriores nunca são alterados (a bronze é imutável).

    Parameters
    ----------
    source : str
        Nome da fonte (subdiretório em ``bronze``), ex.: ``"sgs_ipca"``.
    fetch : Callable[[], list[Any]]
        Função sem argumentos que devolve os registros brutos.
    bronze_dir : Path
        Raiz da camada bronze.
    snapshot_date : date
        Data do snapshot.
    force : bool, optional
        Se ``True``, refaz o snapshot do dia mesmo que válido, by default ``False``.
    metadata : dict[str, Any] | None, optional
        Informações extras registradas no manifesto (parâmetros da consulta).

    Returns
    -------
    Path
        Diretório do snapshot.

    Raises
    ------
    IngestionError
        Se a fonte devolver zero registros.

    Examples
    --------
    >>> ingest_source("sgs_ipca", lambda: [], Path("data/bronze"), date.today())  # doctest: +SKIP
    """
    snapshot_dir = bronze_dir / source / snapshot_date.isoformat()
    if not force and is_snapshot_valid(snapshot_dir):
        logger.info("Cache: snapshot de %s já existe em %s", source, snapshot_dir)
        return snapshot_dir

    records = fetch()
    if not records:
        raise IngestionError(f"A fonte '{source}' devolveu zero registros")

    data_path = snapshot_dir / DATA_FILE
    write_json_atomic(records, data_path)
    manifest = {
        "source": source,
        "snapshot_date": snapshot_date.isoformat(),
        "fetched_at": datetime.now(tz=timezone.utc).isoformat(),
        "n_records": len(records),
        "sha256": hash_file(data_path),
        **(metadata or {}),
    }
    write_json_atomic(manifest, snapshot_dir / MANIFEST_FILE)
    logger.info("Snapshot gravado: %s (%d registros)", snapshot_dir, len(records))
    return snapshot_dir


def find_latest_snapshot(bronze_dir: Path, source: str) -> Path:
    """Localiza o snapshot válido mais recente de uma fonte.

    Parameters
    ----------
    bronze_dir : Path
        Raiz da camada bronze.
    source : str
        Nome da fonte.

    Returns
    -------
    Path
        Diretório do snapshot mais recente com hash íntegro.

    Raises
    ------
    IngestionError
        Se não houver nenhum snapshot válido (rode ``ingest`` antes).

    Examples
    --------
    >>> find_latest_snapshot(Path("data/bronze"), "sgs_ipca")  # doctest: +SKIP
    """
    source_dir = bronze_dir / source
    candidates = sorted((p for p in source_dir.glob("*") if p.is_dir()), reverse=True)
    for candidate in candidates:
        if is_snapshot_valid(candidate):
            return candidate
    raise IngestionError(f"Nenhum snapshot válido para '{source}' em {source_dir}. Rode 'ingest'.")


def load_snapshot_records(snapshot_dir: Path) -> list[dict[str, Any]]:
    """Lê os registros brutos de um snapshot.

    Parameters
    ----------
    snapshot_dir : Path
        Diretório do snapshot.

    Returns
    -------
    list[dict[str, Any]]
        Registros como foram recebidos da API.

    Examples
    --------
    >>> load_snapshot_records(Path("data/bronze/sgs_ipca/2026-01-01"))  # doctest: +SKIP
    """
    records = json.loads((snapshot_dir / DATA_FILE).read_text(encoding="utf-8"))
    return list(records)


def ingest_all(
    settings: Settings,
    client: BcbClient,
    snapshot_date: date,
    force: bool = False,
) -> dict[str, Path]:
    """Ingere todas as séries SGS configuradas e o Focus.

    Parameters
    ----------
    settings : Settings
        Configuração validada.
    client : BcbClient
        Cliente das APIs do BCB.
    snapshot_date : date
        Data do snapshot (normalmente hoje).
    force : bool, optional
        Refaz os snapshots do dia, by default ``False``.

    Returns
    -------
    dict[str, Path]
        Diretório do snapshot por fonte.

    Examples
    --------
    >>> ingest_all(settings, BcbClient(settings.data), date.today())  # doctest: +SKIP
    """
    bronze = settings.paths.data_bronze
    snapshots: dict[str, Path] = {}
    for cfg in settings.series:
        source = f"sgs_{cfg.name}"
        snapshots[source] = ingest_source(
            source,
            lambda code=cfg.sgs_code: client.fetch_sgs(
                code, settings.data.start_date, snapshot_date
            ),
            bronze,
            snapshot_date,
            force,
            metadata={"sgs_code": cfg.sgs_code, "start_date": settings.data.start_date.isoformat()},
        )
    focus = settings.focus
    snapshots["focus"] = ingest_source(
        "focus",
        lambda: client.fetch_focus(focus.indicator, focus.base_calculo),
        bronze,
        snapshot_date,
        force,
        metadata={"indicator": focus.indicator, "base_calculo": focus.base_calculo},
    )
    return snapshots
