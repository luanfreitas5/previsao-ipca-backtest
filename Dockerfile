# syntax=docker/dockerfile:1.7
# Imagem do pipeline (job em lote, sem API): código + dependências travadas no uv.lock.
# Dados (data/), relatórios (reports/) e experimentos (mlruns/) NÃO entram na imagem:
# são montados como volumes em tempo de execução (veja `make docker-run`).
# Tags fixadas por patch; em produção acrescente @sha256:<digest>
# (obtido com `docker buildx imagetools inspect <imagem>:<tag>`). Mesma tag nos dois estágios.

# ---------- Estágio 1: binário do uv, versão fixa (a mesma que gerou o uv.lock) ----------
FROM ghcr.io/astral-sh/uv:0.13.0 AS uv

# ---------- Estágio 2: resolve o ambiente a partir do uv.lock ----------
FROM python:3.12.11-slim-bookworm AS builder
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0
WORKDIR /app
# Só os manifestos: esta camada fica em cache até o lock mudar.
# --locked falha se o uv.lock estiver desatualizado em relação ao pyproject.toml.
# --no-default-groups deixa de fora dev, quality e docs (todos são grupos padrão neste projeto).
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    uv sync --locked --no-default-groups --no-install-project

# ---------- Estágio 3: runtime enxuto, sem uv, sem compiladores ----------
FROM python:3.12.11-slim-bookworm AS runtime
# libgomp1: runtime OpenMP exigido pelo lightgbm; ausente na imagem slim.
# hadolint ignore=DL3008
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app
WORKDIR /app
# Código e venv pertencem ao root: o usuário da aplicação só lê
COPY --from=builder /app/.venv /app/.venv
COPY src/ src/
COPY configs/ configs/
# Diretórios de saída pertencem ao usuário da aplicação ANTES do USER:
# volumes nomeados herdam essa permissão (bind mounts seguem a do host).
RUN mkdir -p data/bronze data/silver data/gold reports/figures reports/tables logs mlruns \
    && chown -R app:app data reports logs mlruns
ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONPATH="/app/src" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONHASHSEED=42 \
    MPLCONFIGDIR=/tmp/matplotlib \
    NUMBA_CACHE_DIR=/tmp/numba
USER app:app
# Job em lote: sem EXPOSE/HEALTHCHECK. O estágio é argumento: `docker run <img> backtest`.
ENTRYPOINT ["python", "src/main.py"]
CMD ["all"]
