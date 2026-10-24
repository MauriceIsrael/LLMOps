.PHONY: verify-suite e2e-suite verify-proposals quick serve demo demo-check install models-fetch eval-semantic test test-all test-docker test-env-check test-unit test-contract test-integration test-e2e typecheck lint snapshot verify hooks eval-check check-names contract-server

install:
	poetry install

snapshot:
	poetry run python scripts/export_sealed_snapshot.py

# Reference demo (examples/nordwave-mcx-2027/): the code hard-codes no project, the demo
# engagement and blueprint are passed through the environment.
DEMO_ENV = LLMOPS_ENGAGEMENT=nordwave-mcx-2027 LLMOPS_BLUEPRINT=BLU-hla-mcx

demo: install
	$(DEMO_ENV) poetry run python -m pipelines.ingestion.migrate_adr0015
	$(DEMO_ENV) poetry run elicit publish
	@echo "Starting MCP Server with SERVER_TOKEN=llmops-dev-token-2026..."
	$(DEMO_ENV) SERVER_TOKEN=llmops-dev-token-2026 poetry run python mcp_server/main.py

demo-check:
	@poetry run python -c "import os; from mcp_server.knowledge.tools import get_graph_summary; res = get_graph_summary(); count = res.get('data', {}).get('knowledge', {}).get('node_counts', {}).get('Asset', 0); print(f'Knowledge Asset Count: {count}'); assert count > 0, 'Asset count must be > 0'; os._exit(0)"

test:
	poetry run pytest tests/contract tests/unit tests/integration tests/e2e -v

# Everything the repository tests, except the evaluations that need a model (tests/evals). This is the suite of docs/TESTING.md.
test-all:
	poetry run pytest tests --ignore=tests/evals -p no:cacheprovider -q -rfEs

# The same suite in a clean container, on dependencies installed from the lock (docs/TESTING.md, "Clean slate").
test-docker:
	docker build -f docker/Dockerfile.test -t llmops-test:latest .
	docker run --rm llmops-test:latest

# Fails with a plain message when the environment does not match the lock (graph engine out of range, runtime leftovers).
test-env-check:
	poetry run pytest tests/unit/test_ladybug_version_guard.py -q -p no:cacheprovider

test-unit:
	poetry run pytest tests/unit -v

test-contract:
	poetry run pytest tests/contract -v

test-integration:
	poetry run pytest tests/integration -v

# End-to-end scenarios of the reference demo (the only tests reading examples/).
test-e2e:
	poetry run pytest tests/e2e -v

# Fast local gate, a few seconds: what the pre-push hook runs. The CI (.github/workflows/tests.yml) runs everything else.
quick:
	poetry run ruff check .
	poetry run python scripts/check_no_project_names.py

# Lint + types + frozen contract + unit tests, to run by hand before a change that touches a contract (the CI runs the whole suite).
verify: lint test-contract test-unit

# Seeded server (scratch copy, SQLite governance) for client contract tests, e.g. Archinex.
contract-server:
	poetry run python scripts/contract_server.py

# Cross-check with the Document Engine (a sibling checkout, or DOCUMENT_ENGINE_DIR; `npm ci` done there): shared vectors, seals of
# the Hub's witnesses recomputed by its code, verdict of its conformity reader. Exit 3 = NOT verified (never a silent green).
verify-suite:
	poetry run python scripts/verify_suite.py

# The K7 example of proposals read with the suite's own schema (sibling checkout of requirements-intake, or REQUIREMENTS_INTAKE_DIR). Exit 3 = NOT verified.
verify-proposals:
	poetry run python scripts/verify_proposals.py

# End-to-end, local: Hub engagement snapshot -> projection -> Document Engine CLI -> HLD (same sibling checkout as verify-suite). Exit 3 = NOT verified.
e2e-suite:
	poetry run python scripts/e2e_suite.py

# Option judge evaluation: recall of expected violations on the annotated dataset.
eval-check:
	poetry run python scripts/eval/eval_check_option.py

# Local semantic search (issue #94): fetch the pinned embedding model once (data/models/, git-ignored), then the
# FR->EN evaluation with the real model (recall at 5, hybrid vs lexical). Run it on demand and nightly.
models-fetch:
	poetry run kb models fetch

eval-semantic:
	poetry run python scripts/eval/eval_semantic_search.py --verbose
	KB_SEMANTIC_EVAL=1 poetry run pytest tests/eval/test_semantic_fr_en.py -m semantic_eval -v

# Install the git pre-push hook that runs `make quick` (ruff + project-name guard; tests and types are the CI's job).
hooks:
	git config core.hooksPath .githooks
	@echo "pre-push hook installed (.githooks/pre-push runs make quick)"

typecheck:
	poetry run mypy mcp_server tools pipelines

lint: typecheck check-names
	poetry run ruff check .

# No project name in the generic code (.project-names-denylist).
check-names:
	poetry run python scripts/check_no_project_names.py

build-gcp:
	gcloud builds submit --config=cloudbuild.yaml --substitutions=_TAG=latest .

deploy-gcp: build-gcp

# Local HTTP server for Archinex (governance, persistent SQLite): see README "Run the governance server locally"
serve:
	poetry run python scripts/serve_local.py
