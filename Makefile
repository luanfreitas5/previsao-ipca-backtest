# --- Configuração ----------------------------------------------------------
# 'src' vira raiz do path ao rodar o script
RUN := uv run python src/main.py

# PYTHONHASHSEED precisa ser exportado ANTES do interpretador iniciar.
export PYTHONHASHSEED := 42

.DEFAULT_GOAL := help
.PHONY: help init venv install update lock export \
	lint typecheck security deadcode complexity docstrings modernize quality check \
	test smoke test-all coverage hooks pre-commit update-hooks release \
	docs docs-serve docs-deploy profile clean cache jupyter add remove tree \
	ingest silver gold backtest report pipeline \
	clean-gold clean-reports clean-outputs mlflow

help:  ## Lista os alvos disponíveis
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

init:  ## Inicializa o projeto (instala dependências + hooks)
	$(MAKE) install
	$(MAKE) hooks

venv:  ## Cria o ambiente virtual (requer: uv)
	uv venv

install:  ## Instala dependências (runtime + dev)
	uv sync --dev

update:  ## Atualiza todas as dependências e sincroniza
	uv lock --upgrade
	uv sync --all-groups

lock:  ## Gera/atualiza o uv.lock
	uv lock

export:  ## Exporta requirements.txt (para quem usa pip)
	uv export --no-hashes -o requirements.txt

# --- Pipeline ---------------------------------------------------------------
ingest:  ## Baixa SGS + Focus para data/bronze (idempotente; FORCE=1 refaz o snapshot do dia)
	$(RUN) ingest $(if $(FORCE),--force,)

silver:  ## Limpa e valida bronze -> silver
	$(RUN) silver

gold:  ## Constrói o ledger point-in-time e a tabela supervisionada (silver -> gold)
	$(RUN) gold

backtest:  ## Roda o backtest walk-forward, conformal e MLflow
	$(RUN) backtest

report:  ## Gera tabelas, figuras e reports/relatorio_final.md
	$(RUN) report

pipeline:  ## Executa o fluxo completo: ingest -> silver -> gold -> backtest -> report
	$(RUN) all

# --- Qualidade -------------------------------------------------------------
lint:  ## Lint com ruff (format + check --fix)
	uv run ruff format .
	uv run ruff check --fix .

typecheck:  ## Type checking estático (basedPyright)
	uv run basedpyright

security:  ## Análise de segurança (bandit + pip-audit)
	uv run bandit -r src -c pyproject.toml
	uv run pip-audit

deadcode:  ## Detecta código morto (vulture)
	uv run vulture src

complexity:  ## Limites de complexidade (xenon)
	uv run xenon --max-absolute B --max-modules A --max-average A src

docstrings:  ## Cobertura de docstrings (interrogate)
	uv run interrogate -v src

modernize:  ## Sugestões de modernização (refurb)
	uv run refurb src

quality: lint typecheck security deadcode complexity docstrings modernize  ## Suíte de qualidade completa

check: quality test  ## Roda localmente o mesmo que o CI (qualidade + testes)

# --- Testes ----------------------------------------------------------------
test:  ## Roda os testes com cobertura (sem os lentos)
	uv run pytest -m "not slow"

smoke:  ## Roda apenas os smoke tests
	uv run pytest -m smoke -q --no-cov

test-all:  ## Roda a suíte completa, inclusive os testes lentos
	uv run pytest

coverage:  ## Gera o relatório de cobertura em HTML
	uv run pytest -m "not slow" --cov-report=html
	@echo "Relatório disponível em htmlcov/index.html"

hooks:  ## Instala os hooks do pre-commit
	uv run pre-commit install
	uv run pre-commit install --hook-type commit-msg
	uv run detect-secrets scan > .secrets.baseline

pre-commit:  ## Roda todos os hooks do pre-commit em todos os arquivos
	uv run pre-commit run --all-files

update-hooks:  ## Atualiza as versões dos hooks do pre-commit
	uv run pre-commit autoupdate

release:  ## Cria uma nova release (versão + changelog + tag)
	uv run cz bump --changelog

# --- Limpeza (a camada bronze nunca é apagada) -------------------------------
clean-gold:  ## Remove os dados derivados da camada gold
	rm -f data/gold/*.parquet

clean-reports:  ## Remove tabelas e figuras geradas
	rm -rf reports/tables reports/figures/*.png reports/figures/*.svg

clean-outputs: clean-gold clean-reports  ## Remove todas as saídas do pipeline

clean:  ## Remove caches e artefatos temporários
	rm -rf .pytest_cache .ruff_cache htmlcov coverage.xml site
	find . -type d -name __pycache__ -not -path "./.venv/*" -exec rm -rf {} +

cache:  ## Limpa o cache do uv
	uv cache clean

# --- Documentação ----------------------------------------------------------
docs:  ## Constrói a documentação (modo estrito)
	uv run mkdocs build --strict

docs-serve:  ## Servidor local da documentação
	uv run mkdocs serve

docs-deploy:  ## Publica a documentação no GitHub Pages
	uv run mkdocs gh-deploy --force

# --- Utilitários -----------------------------------------------------------
profile:  ## Profiling com scalene
	uv run scalene src/main.py backtest

jupyter:  ## Abre o JupyterLab
	uv run jupyter lab

mlflow:  ## Sobe a interface do MLflow (http://localhost:5000)
	uv run mlflow ui --backend-store-uri sqlite:///mlruns/mlflow.db

add:  ## Adiciona dependência: make add PKG=nome
	uv add $(PKG)

remove:  ## Remove dependência: make remove PKG=nome
	uv remove $(PKG)

tree:  ## Árvore de dependências
	uv tree
