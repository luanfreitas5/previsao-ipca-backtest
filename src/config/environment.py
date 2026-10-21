"""Reprodutibilidade: fixa as fontes de aleatoriedade do processo."""

import os
import random

import numpy as np


def seed_everything(seed: int = 42) -> None:
    """Fixa ``random``, ``numpy`` e ``PYTHONHASHSEED``.

    O ``PYTHONHASHSEED`` só tem efeito pleno se exportado antes de iniciar o
    interpretador (o ``Makefile`` faz isso); aqui ele é gravado para subprocessos.

    Parameters
    ----------
    seed : int, optional
        Semente global, by default 42.

    Examples
    --------
    >>> seed_everything(42)
    """
    os.environ["PYTHONHASHSEED"] = str(seed)
    random.seed(seed)
    np.random.seed(seed)  # noqa: NPY002 - semente global para bibliotecas legadas
