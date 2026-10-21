"""Cliente das APIs públicas do Banco Central: SGS (séries) e Olinda (Focus)."""

import logging
import time
from collections.abc import Callable
from datetime import date, timedelta
from typing import Any
from urllib.parse import quote, urlencode

import httpx

from config.settings import DataConfig
from exceptions.data import IngestionError
from utils.dates import add_months

logger = logging.getLogger(__name__)

_RETRYABLE_STATUS = {429, 500, 502, 503, 504}
FOCUS_FIELDS = "Data,DataReferencia,Mediana,Media,DesvioPadrao,Minimo,Maximo,numeroRespondentes"


class BcbClient:
    """Cliente HTTP com retry exponencial e paginação para as APIs do BCB.

    Parameters
    ----------
    config : DataConfig
        URLs, timeout, tentativas e tamanho das janelas.
    client : httpx.Client | None, optional
        Cliente HTTP injetável (testes usam ``httpx.MockTransport``).
    sleep : Callable[[float], None], optional
        Função de espera entre tentativas (injetável para testes).

    Examples
    --------
    >>> client = BcbClient(settings.data)  # doctest: +SKIP
    >>> client.fetch_sgs(433, date(2020, 1, 1), date(2020, 12, 31))  # doctest: +SKIP
    """

    def __init__(
        self,
        config: DataConfig,
        client: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._config = config
        self._client = client or httpx.Client(timeout=config.request_timeout_s)
        self._sleep = sleep

    def fetch_sgs(self, code: int, start: date, end: date) -> list[dict[str, str]]:
        """Baixa uma série SGS em janelas de ``chunk_years`` anos.

        A API limita a janela de consulta de séries diárias, por isso o período
        é fatiado em blocos consecutivos e sem sobreposição.

        Parameters
        ----------
        code : int
            Código da série no SGS.
        start : date
            Data inicial (inclusive).
        end : date
            Data final (inclusive).

        Returns
        -------
        list[dict[str, str]]
            Registros ``{"data": "dd/MM/yyyy", "valor": "..."}`` exatamente como recebidos.

        Raises
        ------
        IngestionError
            Se a API falhar após todas as tentativas.
        """
        url = f"{self._config.sgs_base_url}/bcdata.sgs.{code}/dados"
        records: list[dict[str, str]] = []
        for window_start, window_end in self._build_windows(start, end):
            params = {
                "formato": "json",
                "dataInicial": window_start.strftime("%d/%m/%Y"),
                "dataFinal": window_end.strftime("%d/%m/%Y"),
            }
            payload = self._get_json(url, params)
            if not isinstance(payload, list):
                raise IngestionError(f"Resposta inesperada do SGS {code}: {payload!r}")
            records.extend(payload)
        logger.info("SGS %s: %d registros baixados", code, len(records))
        return records

    def fetch_focus(self, indicator: str, base_calculo: int) -> list[dict[str, Any]]:
        """Baixa as expectativas mensais do Focus (Olinda) com paginação OData.

        Parameters
        ----------
        indicator : str
            Indicador (ex.: ``"IPCA"``).
        base_calculo : int
            0 = estatísticas dos últimos 30 dias; 1 = últimos 5 dias úteis.

        Returns
        -------
        list[dict[str, Any]]
            Registros exatamente como recebidos.

        Raises
        ------
        IngestionError
            Se a API falhar após todas as tentativas.
        """
        url = f"{self._config.olinda_url}/ExpectativaMercadoMensais"
        page_size = self._config.focus_page_size
        records: list[dict[str, Any]] = []
        skip = 0
        while True:
            params = {
                "$filter": f"Indicador eq '{indicator}' and baseCalculo eq {base_calculo}",
                "$select": FOCUS_FIELDS,
                "$orderby": "Data asc,DataReferencia asc",
                "$format": "json",
                "$top": str(page_size),
                "$skip": str(skip),
            }
            payload = self._get_json(url, params)
            page = payload.get("value", []) if isinstance(payload, dict) else None
            if page is None:
                raise IngestionError(f"Resposta inesperada do Focus: {payload!r}")
            records.extend(page)
            if len(page) < page_size:
                break
            skip += page_size
        logger.info("Focus %s: %d registros baixados", indicator, len(records))
        return records

    def _build_windows(self, start: date, end: date) -> list[tuple[date, date]]:
        """Fatia ``[start, end]`` em janelas consecutivas de ``chunk_years`` anos."""
        windows: list[tuple[date, date]] = []
        cursor = start
        while cursor <= end:
            next_start = add_months(cursor.replace(day=1), 12 * self._config.chunk_years)
            window_end = min(next_start - timedelta(days=1), end)
            windows.append((cursor, window_end))
            cursor = window_end + timedelta(days=1)
        return windows

    def _fetch_json_once(self, url: str, params: dict[str, str]) -> Any:
        """Executa um único GET; levanta ``HTTPStatusError`` em status de erro/retentável."""
        # O Olinda não aceita "+" como espaço (httpx o usa por padrão): exige %20
        response = self._client.get(f"{url}?{urlencode(params, quote_via=quote)}")
        if response.status_code in _RETRYABLE_STATUS:
            raise httpx.HTTPStatusError(
                f"status {response.status_code}", request=response.request, response=response
            )
        response.raise_for_status()
        return response.json()

    def _get_json(self, url: str, params: dict[str, str]) -> Any:
        """GET com retry exponencial em erros transitórios (rede, 429, 5xx)."""
        attempts = self._config.max_retries + 1
        last_error: Exception | None = None
        for attempt in range(attempts):
            try:
                return self._fetch_json_once(url, params)
            except (httpx.TransportError, httpx.HTTPStatusError, ValueError) as error:  # noqa: PERF203 - retry
                last_error = error
                logger.warning(
                    "Falha na requisição (tentativa %d/%d): %s", attempt + 1, attempts, error
                )
                if isinstance(error, httpx.HTTPStatusError) and error.response.status_code < 500:
                    logger.warning(
                        "Corpo da resposta (HTTP %d): %s",
                        error.response.status_code,
                        error.response.text[:500],
                    )
                if attempt < attempts - 1:
                    self._sleep(self._config.backoff_s * 2**attempt)
        raise IngestionError(f"Falha ao acessar {url} após {attempts} tentativas") from last_error
