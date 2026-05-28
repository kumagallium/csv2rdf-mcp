# Self-built csv2rdf-mcp upload API image (Phase 2).
#
# Bundles the FastAPI service + the watcher loop into a single Python process.
# Both packages live in the monorepo (api/ + ingest/), so build context MUST be
# the repo root.
#
# Build:
#   docker build -f infra/upload-api/Dockerfile -t csv2rdf-upload-api .
#
# Crucible compatibility: legacy docker builder (no BuildKit). We use
# ``COPY`` + ``RUN chmod`` instead of ``COPY --chmod`` for the same reason
# as ``infra/togomcp/Dockerfile``.

FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install the sibling packages in dependency order: ingest first, then api
# (which depends on csv2rdf-ingest). The api/pyproject.toml uses
# ``[tool.uv.sources]`` for local dev under uv; pip relies on the fact that
# csv2rdf-ingest is already installed when it resolves the api package.
COPY ingest/pyproject.toml /app/ingest/pyproject.toml
COPY ingest/src /app/ingest/src
COPY api/pyproject.toml /app/api/pyproject.toml
COPY api/src /app/api/src

RUN pip install /app/ingest \
    && pip install /app/api

# Non-root runtime. /data/sources is provided by compose volume; the watcher
# auto-creates per-kind subdirs on startup.
RUN useradd --create-home --uid 1000 csv2rdfapi \
    && mkdir -p /data/sources \
    && chown -R csv2rdfapi:csv2rdfapi /data/sources

USER csv2rdfapi
WORKDIR /home/csv2rdfapi

EXPOSE 8080

# csv2rdf-api invokes uvicorn with the factory-mode app builder.
CMD ["csv2rdf-api", "--host", "0.0.0.0", "--port", "8080"]
