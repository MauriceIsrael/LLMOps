# Dockerfile optimisé pour le serveur FastMCP LLMOps (GCP Cloud Run / Artifact Registry)
FROM python:3.11-slim

WORKDIR /app

# Dépendances système C++ requises par LadybugDB et build tools (x86_64)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    g++ \
    libstdc++6 \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir poetry

# Ingestion de la configuration et verrou de dépendances
COPY pyproject.toml poetry.lock* README.md ./

RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --no-root --without dev,eval

# Copie des dossiers de l'application
COPY mcp_server ./mcp_server
COPY pipelines ./pipelines
COPY tools ./tools
COPY data ./data
COPY schemas ./schemas
COPY fixtures ./fixtures
COPY scripts ./scripts

RUN poetry install --no-interaction --no-ansi --only-root

# Variables d'environnement pour GCP Cloud Run et LadybugDB backend
ENV GRAPH_BACKEND=ladybug
ENV LLMOPS_PLANE=all
ENV LLMOPS_TRANSPORT=sse
ENV PORT=8000
ENV HOST=0.0.0.0

# Ingestion et migration déterministe de la base de connaissances (Knowledge Plane)
RUN poetry run python -m pipelines.ingestion.migrate_adr0015
RUN poetry run python scripts/export_sealed_snapshot.py
RUN poetry run python -c "import os; from mcp_server.knowledge.tools import get_graph_summary; res = get_graph_summary(); count = res.get('data', {}).get('knowledge', {}).get('node_counts', {}).get('Asset', 0); print(f'✅ Build Verification — Knowledge Asset Count: {count}'); assert count > 0, f'Asset count is {count}'; os._exit(0)"

EXPOSE 8000

# Health check conteneur utilisant l'endpoint HTTP /health
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

CMD ["poetry", "run", "mcp-server"]
