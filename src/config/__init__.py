"""Configuração do projeto: YAML validado com Pydantic, logging e reprodutibilidade.

Módulos
-------
paths
    Constantes ``ROOT`` e ``CONFIG_DIR``.
settings
    ``Settings`` e ``load_settings`` (carrega e valida ``configs/*.yaml`` e ``.env``).
logging_setup
    ``configure_logging`` (console com rich + arquivo diário).
environment
    ``seed_everything`` (fixa todas as fontes de aleatoriedade).
"""
