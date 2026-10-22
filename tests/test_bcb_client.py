"""Testes do cliente do BCB com transporte HTTP simulado (sem rede)."""

from datetime import date

import httpx
import pytest

from config.settings import DataConfig, Settings
from data.bcb_client import BcbClient
from exceptions.data import IngestionError


def make_client(handler, config: DataConfig, sleeps: list[float] | None = None) -> BcbClient:
    http = httpx.Client(transport=httpx.MockTransport(handler))
    record = sleeps if sleeps is not None else []
    return BcbClient(config, http, sleep=record.append)


@pytest.fixture
def config(settings: Settings) -> DataConfig:
    return settings.data.model_copy(update={"chunk_years": 5, "max_retries": 2, "backoff_s": 1.0})


def test_fetch_sgs_splits_into_non_overlapping_windows(config: DataConfig):
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(dict(request.url.params))
        return httpx.Response(200, json=[{"data": "01/01/2000", "valor": "0.1"}])

    client = make_client(handler, config)
    records = client.fetch_sgs(433, date(2000, 1, 1), date(2012, 6, 30))

    assert len(calls) == 3
    assert (calls[0]["dataInicial"], calls[0]["dataFinal"]) == ("01/01/2000", "31/12/2004")
    assert (calls[1]["dataInicial"], calls[1]["dataFinal"]) == ("01/01/2005", "31/12/2009")
    assert (calls[2]["dataInicial"], calls[2]["dataFinal"]) == ("01/01/2010", "30/06/2012")
    assert len(records) == 3


def test_retries_with_exponential_backoff(config: DataConfig):
    attempts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        if attempts["n"] < 3:
            return httpx.Response(503)
        return httpx.Response(200, json=[{"data": "01/01/2020", "valor": "0.2"}])

    sleeps: list[float] = []
    client = make_client(handler, config, sleeps)
    assert client.fetch_sgs(433, date(2020, 1, 1), date(2020, 12, 31))
    assert attempts["n"] == 3
    assert sleeps == [1.0, 2.0]


def test_raises_after_exhausting_retries(config: DataConfig):
    client = make_client(lambda request: httpx.Response(500), config)
    with pytest.raises(IngestionError):
        client.fetch_sgs(433, date(2020, 1, 1), date(2020, 12, 31))


def test_non_retryable_status_still_fails(config: DataConfig):
    client = make_client(lambda request: httpx.Response(404), config)
    with pytest.raises(IngestionError):
        client.fetch_sgs(433, date(2020, 1, 1), date(2020, 12, 31))


def test_unexpected_sgs_payload_is_an_error(config: DataConfig):
    client = make_client(lambda request: httpx.Response(200, json={"erro": "x"}), config)
    with pytest.raises(IngestionError):
        client.fetch_sgs(433, date(2020, 1, 1), date(2020, 12, 31))


def test_focus_pagination_collects_every_page(config: DataConfig):
    config = config.model_copy(update={"focus_page_size": 2})
    data = [
        {"Data": f"2020-01-{d:02d}", "DataReferencia": "02/2020", "Mediana": 0.2}
        for d in range(1, 6)
    ]
    skips = []

    def handler(request: httpx.Request) -> httpx.Response:
        skip = int(request.url.params["$skip"])
        skips.append(skip)
        assert "Indicador eq 'IPCA'" in request.url.params["$filter"]
        return httpx.Response(200, json={"value": data[skip : skip + 2]})

    records = make_client(handler, config).fetch_focus("IPCA", 0)
    assert records == data
    assert skips == [0, 2, 4]


def test_unexpected_focus_payload_is_an_error(config: DataConfig):
    client = make_client(lambda request: httpx.Response(200, json=[1, 2]), config)
    with pytest.raises(IngestionError):
        client.fetch_focus("IPCA", 0)
