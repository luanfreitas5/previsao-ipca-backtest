"""Aritmética de meses usada na construção de origens, alvos e disponibilidade."""

import calendar
from datetime import date


def month_start(value: date) -> date:
    """Retorna o primeiro dia do mês de ``value``.

    Parameters
    ----------
    value : date
        Data de entrada.

    Returns
    -------
    date
        Primeiro dia do mesmo mês.

    Examples
    --------
    >>> month_start(date(2020, 3, 17))
    datetime.date(2020, 3, 1)
    """
    return value.replace(day=1)


def month_end(value: date) -> date:
    """Retorna o último dia do mês de ``value``.

    Parameters
    ----------
    value : date
        Data de entrada.

    Returns
    -------
    date
        Último dia do mesmo mês.

    Examples
    --------
    >>> month_end(date(2020, 2, 10))
    datetime.date(2020, 2, 29)
    """
    return value.replace(day=calendar.monthrange(value.year, value.month)[1])


def add_months(value: date, months: int) -> date:
    """Desloca ``value`` em ``months`` meses e retorna o PRIMEIRO dia do mês resultante.

    Parameters
    ----------
    value : date
        Data de entrada (apenas ano e mês importam).
    months : int
        Deslocamento em meses (pode ser negativo).

    Returns
    -------
    date
        Primeiro dia do mês deslocado.

    Examples
    --------
    >>> add_months(date(2020, 11, 30), 3)
    datetime.date(2021, 2, 1)
    """
    total = value.year * 12 + (value.month - 1) + months
    return date(total // 12, total % 12 + 1, 1)


def months_between(start: date, end: date) -> int:
    """Número de meses de calendário de ``start`` até ``end`` (pode ser negativo).

    Parameters
    ----------
    start : date
        Data inicial.
    end : date
        Data final.

    Returns
    -------
    int
        ``(ano_end - ano_start) * 12 + (mês_end - mês_start)``.

    Examples
    --------
    >>> months_between(date(2020, 1, 31), date(2020, 4, 1))
    3
    """
    return (end.year - start.year) * 12 + (end.month - start.month)


def generate_month_ends(first: date, last: date) -> list[date]:
    """Gera todos os fins de mês entre ``first`` e ``last`` (inclusive, por mês).

    Parameters
    ----------
    first : date
        Data do primeiro mês.
    last : date
        Data do último mês.

    Returns
    -------
    list[date]
        Fins de mês em ordem crescente (vazia se ``last`` < ``first``).

    Examples
    --------
    >>> generate_month_ends(date(2020, 1, 31), date(2020, 3, 1))
    [datetime.date(2020, 1, 31), datetime.date(2020, 2, 29), datetime.date(2020, 3, 31)]
    """
    count = months_between(first, last) + 1
    return [month_end(add_months(first, i)) for i in range(max(count, 0))]
