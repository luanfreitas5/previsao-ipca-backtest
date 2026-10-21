"""Hashes SHA-256 para rastrear a versão exata dos dados."""

import hashlib
from pathlib import Path

_CHUNK_SIZE = 1024 * 1024


def hash_bytes(content: bytes) -> str:
    """Calcula o SHA-256 de um bloco de bytes.

    Parameters
    ----------
    content : bytes
        Conteúdo a ser resumido.

    Returns
    -------
    str
        Hash hexadecimal de 64 caracteres.

    Examples
    --------
    >>> len(hash_bytes(b"abc"))
    64
    """
    return hashlib.sha256(content).hexdigest()


def hash_file(path: Path) -> str:
    """Calcula o SHA-256 de um arquivo lendo em blocos (memória constante).

    Parameters
    ----------
    path : Path
        Caminho do arquivo.

    Returns
    -------
    str
        Hash hexadecimal de 64 caracteres.

    Raises
    ------
    FileNotFoundError
        Se o arquivo não existir.

    Examples
    --------
    >>> hash_file(Path("data/bronze/sgs/ipca/2026-01-01/data.json"))  # doctest: +SKIP
    """
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while chunk := handle.read(_CHUNK_SIZE):
            digest.update(chunk)
    return digest.hexdigest()
