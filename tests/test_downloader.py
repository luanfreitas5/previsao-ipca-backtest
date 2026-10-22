"""Testes da ingestão idempotente para a bronze."""

import json
from datetime import date
from pathlib import Path

import pytest

from config.settings import Settings
from data.bcb_client import BcbClient
from data.downloader import (
    DATA_FILE,
    find_latest_snapshot,
    ingest_all,
    ingest_source,
    is_snapshot_valid,
    load_snapshot_records,
)
from exceptions.data import IngestionError

RECORDS = [{"data": "01/01/2020", "valor": "0.21"}]


class Counter:
    """Fonte falsa que conta quantas vezes foi consultada."""

    def __init__(self, records=RECORDS):
        self.calls = 0
        self.records = records

    def __call__(self):
        self.calls += 1
        return self.records


@pytest.mark.smoke
def test_second_run_uses_cache(tmp_path: Path):
    fetch = Counter()
    first = ingest_source("sgs_ipca", fetch, tmp_path, date(2026, 1, 5))
    second = ingest_source("sgs_ipca", fetch, tmp_path, date(2026, 1, 5))
    assert first == second
    assert fetch.calls == 1
    assert is_snapshot_valid(first)
    assert load_snapshot_records(first) == RECORDS


def test_manifest_records_hash_and_metadata(tmp_path: Path):
    snapshot = ingest_source(
        "sgs_ipca", Counter(), tmp_path, date(2026, 1, 5), metadata={"sgs_code": 433}
    )
    manifest = json.loads((snapshot / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["n_records"] == 1
    assert manifest["sgs_code"] == 433
    assert len(manifest["sha256"]) == 64


def test_corrupted_snapshot_is_refetched(tmp_path: Path):
    fetch = Counter()
    snapshot = ingest_source("sgs_ipca", fetch, tmp_path, date(2026, 1, 5))
    (snapshot / DATA_FILE).write_text("[]", encoding="utf-8")
    assert not is_snapshot_valid(snapshot)
    ingest_source("sgs_ipca", fetch, tmp_path, date(2026, 1, 5))
    assert fetch.calls == 2


def test_force_refetches_valid_snapshot(tmp_path: Path):
    fetch = Counter()
    ingest_source("sgs_ipca", fetch, tmp_path, date(2026, 1, 5))
    ingest_source("sgs_ipca", fetch, tmp_path, date(2026, 1, 5), force=True)
    assert fetch.calls == 2


def test_empty_source_is_an_error(tmp_path: Path):
    with pytest.raises(IngestionError):
        ingest_source("sgs_ipca", Counter(records=[]), tmp_path, date(2026, 1, 5))


def test_previous_snapshots_are_never_touched(tmp_path: Path):
    old = ingest_source("sgs_ipca", Counter(), tmp_path, date(2026, 1, 5))
    before = (old / DATA_FILE).read_bytes()
    ingest_source(
        "sgs_ipca", Counter([{"data": "01/02/2020", "valor": "1"}]), tmp_path, date(2026, 1, 6)
    )
    assert (old / DATA_FILE).read_bytes() == before


def test_find_latest_snapshot_skips_invalid(tmp_path: Path):
    good = ingest_source("sgs_ipca", Counter(), tmp_path, date(2026, 1, 5))
    newer = ingest_source("sgs_ipca", Counter(), tmp_path, date(2026, 1, 6))
    (newer / DATA_FILE).write_text("[]", encoding="utf-8")
    assert find_latest_snapshot(tmp_path, "sgs_ipca") == good


def test_find_latest_snapshot_without_data_raises(tmp_path: Path):
    with pytest.raises(IngestionError):
        find_latest_snapshot(tmp_path, "sgs_ipca")


def test_ingest_all_creates_one_snapshot_per_source(tmp_path: Path, settings: Settings):
    class FakeClient(BcbClient):
        def __init__(self) -> None:
            pass

        def fetch_sgs(self, code, start, end):
            return RECORDS

        def fetch_focus(self, indicator, base_calculo):
            return [{"Data": "2020-01-06", "DataReferencia": "02/2020", "Mediana": 0.2}]

    config = settings.model_copy(
        update={"paths": settings.paths.model_copy(update={"data_bronze": tmp_path})}
    )
    snapshots = ingest_all(config, FakeClient(), date(2026, 1, 5))
    assert set(snapshots) == {f"sgs_{n}" for n in settings.series_names} | {"focus"}
    assert all(is_snapshot_valid(p) for p in snapshots.values())
