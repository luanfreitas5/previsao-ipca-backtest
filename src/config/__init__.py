"""Configuração do projeto: YAML validado com Pydantic, logging e reprodutibilidade.

Módulos
-------
paths
    Constantes ``ROOT`` e ``CONFIG_DIR``.
settings
    ``Settings`` e ``load_settings`` (carrega e valida ``configs/*.yaml`` e ``.env``).
logging
    ``configure_logging`` (``dictConfig`` de ``configs/logging.yaml``: console rich + arquivo)
    e ``CONSOLE`` (console compartilhado com as barras de progresso).
environment
    ``seed_everything`` (fixa todas as fontes de aleatoriedade).
"""
