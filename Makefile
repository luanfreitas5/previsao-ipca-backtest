# --- Configuração ----------------------------------------------------------
# `python src/main.py` coloca 'src' na raiz do sys.path
UV := uv
RUN := $(UV) run python src/main.py
IMAGE ?= previsao-ipca-backtest:dev

# PYTHONHASHSEED precisa ser exportado ANTES do interpretador iniciar.
export PYTHONHASHSEED := 42

.DEFAULT_GOAL := help
.PHONY: help init install venv update lock export \
	lint format typecheck security quality check \
	test smoke test-all coverage hooks pre-commit update-hooks release \
	docs docs-serve docs-deploy profile clean cache jupyter add remove tree \
	ingest silver gold backtest report pipeline train reproduce \
	clean-gold clean-reports clean-outputs mlflow docker-build docker-run

help:  ## Lista os alvos disponíveis
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

install:  ## Instala todos os grupos de dependências e os hooks do pre-commit
	$(UV) sync --all-groups
	$(UV) run pre-commit install --hook-type pre-commit --hook-type commit-msg

init: install  ## Alias de install

venv:  ## Cria o ambiente virtual (requer: uv)
	$(UV) venv

update:  ## Atualiza todas as dependências e sincroniza
	$(UV) lock --upgrade
	$(UV) sync --all-groups

lock:  ## Gera/atualiza o uv.lock
	$(UV) lock

export:  ## Exporta requirements.txt (para quem usa pip)
	$(UV) export --locked --no-dev --no-hashes -o requirements.txt

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

train: backtest  ## Alias de backtest (etapa que ajusta e avalia os modelos)

reproduce: pipeline  ## Reproduz o resultado do zero (sem DVC: o pipeline é o DAG)

# --- Qualidade (CI e `make check`) -------------------------------------------
lint:  ## Lint e formatação (somente verifica; use `make format` para corrigir)
	$(UV) run ruff check src tests
	$(UV) run ruff format --check src tests

format:  ## Corrige lint e formata o código
	$(UV) run ruff check --fix src tests
	$(UV) run ruff format src tests

typecheck:  ## Type checking estático (basedPyright)
	$(UV) run basedpyright

security:  ## Análise de segurança (bandit + pip-audit)
	$(UV) run bandit -c pyproject.toml -r src
	$(UV) run pip-audit

quality:  ## Código morto, modernização, complexidade e docstrings
	$(UV) run vulture
	$(UV) run refurb src
	$(UV) run xenon --max-absolute B --max-modules A --max-average A src
	$(UV) run interrogate -v src

check: lint typecheck security quality test  ## Replica o CI localmente

# --- Testes ----------------------------------------------------------------
test:  ## Roda os testes com cobertura (sem os lentos)
	$(UV) run pytest -m "not slow"

smoke:  ## Roda apenas os smoke tests
	$(UV) run pytest -m smoke -q --no-cov

test-all:  ## Roda a suíte completa, inclusive os testes lentos
	$(UV) run pytest

coverage:  ## Gera o relatório de cobertura em HTML
	$(UV) run pytest -m "not slow" --cov-report=html
	@echo "Relatório disponível em htmlcov/index.html"

hooks:  ## Instala os hooks do pre-commit (o baseline de segredos já é versionado)
	$(UV) run pre-commit install --hook-type pre-commit --hook-type commit-msg
	$(UV) run detect-secrets scan > .secrets.baseline

pre-commit:  ## Roda todos os hooks do pre-commit em todos os arquivos
	$(UV) run pre-commit run --all-files

update-hooks:  ## Atualiza as versões dos hooks do pre-commit
	$(UV) run pre-commit autoupdate

release:  ## Cria uma nova release (versão + changelog + tag)
	$(UV) run cz bump --changelog

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
	$(UV) cache clean

# --- Documentação ----------------------------------------------------------
docs:  ## Constrói a documentação (modo estrito)
	$(UV) run mkdocs build --strict

docs-serve:  ## Servidor local da documentação
	$(UV) run mkdocs serve

docs-deploy:  ## Publica a documentação no GitHub Pages
	$(UV) run mkdocs gh-deploy --force

# --- Utilitários -----------------------------------------------------------
profile:  ## Profiling com scalene
	$(UV) run scalene src/main.py backtest

jupyter:  ## Abre o JupyterLab
	$(UV) run jupyter lab

docker-build:  ## Constrói a imagem do pipeline (código + dependências travadas)
	docker build -t $(IMAGE) .

docker-run:  ## Roda um estágio no contêiner: make docker-run STAGE=backtest
	docker run --rm -v "$(CURDIR)/data:/app/data" -v "$(CURDIR)/reports:/app/reports" \
		-v "$(CURDIR)/mlruns:/app/mlruns" $(IMAGE) $(or $(STAGE),all)

mlflow:  ## Sobe a interface do MLflow (http://localhost:5000)
	$(UV) run mlflow ui --backend-store-uri sqlite:///mlruns/mlflow.db

add:  ## Adiciona dependência: make add PKG=nome
	$(UV) add $(PKG)

remove:  ## Remove dependência: make remove PKG=nome
	$(UV) remove $(PKG)

tree:  ## Árvore de dependências
	$(UV) tree
