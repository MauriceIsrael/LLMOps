"""Generate ``schemas/openapi.json`` (OpenAPI 3.1.0) deterministically from the frozen REST shapes (Issue #37).

Usage::

    poetry run python scripts/generate_openapi.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from mcp_server.core.version import CONTRACT_VERSION

FROZEN_DIR = ROOT_DIR / "tests" / "contract" / "frozen"
STATUS_CODES_FILE = FROZEN_DIR / "_status_codes.json"
OUTPUT_PATH = ROOT_DIR / "schemas" / "openapi.json"

PUBLIC_PATHS = {"/health", "/healthz", "/ready", "/readyz", "/.well-known/jwks.json"}
DEPRECATED_PATHS = {
    "/api/documents/zero-draft-blueprint",
    "/api/rfp/shred-to-candidates",
    "/api/rfp/coverage-gaps",
}
PATH_PARAM_RE = re.compile(r"\{([^}:]+)(?::[^}]+)?\}")


DYNAMIC_MAP_KEYS = {"by_domain", "domains"}


def shape_to_json_schema(shape: dict[str, Any] | None, key_name: str | None = None) -> dict[str, Any]:
    """Convert a frozen shape node into an OpenAPI 3.1 JSON Schema object."""
    if not shape or not isinstance(shape, dict):
        return {}
    raw_types = list(shape.get("type") or ["string"])
    schema: dict[str, Any] = {
        "type": raw_types[0] if len(raw_types) == 1 else raw_types,
    }
    if key_name in DYNAMIC_MAP_KEYS and "keys" in shape and isinstance(shape["keys"], dict):
        # Data-keyed dictionaries (e.g. domain -> count or domain -> owner) are maps in OpenAPI
        merged_values: dict[str, Any] = {}
        for v in shape["keys"].values():
            sub = shape_to_json_schema(v)
            if sub:
                merged_values = sub
                break
        schema["additionalProperties"] = merged_values or {"type": "string"}
        return schema

    if "keys" in shape and isinstance(shape["keys"], dict):
        schema["properties"] = {
            k: shape_to_json_schema(v, key_name=k) for k, v in sorted(shape["keys"].items())
        }
    if "values" in shape and shape["values"] is not None:
        schema["additionalProperties"] = shape_to_json_schema(shape["values"])
    if "items" in shape and shape["items"] is not None:
        schema["items"] = shape_to_json_schema(shape["items"])
    return schema


def _normalize_openapi_path(raw_path: str) -> str:
    return re.sub(r"\{([^}:]+):[^}]+\}", r"{\1}", raw_path)


def build_openapi() -> dict[str, Any]:
    """Build the complete OpenAPI 3.1.0 specification from ``tests/contract/frozen/rest.*.shape.json``."""
    status_codes: dict[str, int] = {}
    if STATUS_CODES_FILE.is_file():
        status_codes = json.loads(STATUS_CODES_FILE.read_text(encoding="utf-8"))

    paths: dict[str, dict[str, Any]] = {}
    for shape_file in sorted(FROZEN_DIR.glob("rest.*.shape.json")):
        doc = json.loads(shape_file.read_text(encoding="utf-8"))
        interface: str = doc["interface"]  # "rest.<METHOD> <PATH>"
        _, rest_spec = interface.split("rest.", 1)
        method_str, raw_path = rest_spec.split(" ", 1)
        method = method_str.lower()
        norm_path = _normalize_openapi_path(raw_path)

        body_shape = (doc.get("shape") or {}).get("keys", {}).get("body")
        response_schema = shape_to_json_schema(body_shape)
        code = str(status_codes.get(interface, 200))

        params = [
            {
                "name": match.group(1),
                "in": "path",
                "required": True,
                "schema": {"type": "string"},
            }
            for match in PATH_PARAM_RE.finditer(raw_path)
        ]

        operation: dict[str, Any] = {
            "operationId": f"{method}_{re.sub(r'[^a-zA-Z0-9]+', '_', norm_path).strip('_')}",
            "summary": f"{method_str} {norm_path}",
            "responses": {
                code: {
                    "description": f"Frozen v1 contract response ({interface})",
                    "content": {
                        "application/json": {
                            "schema": response_schema,
                        }
                    },
                }
            },
        }
        if params:
            operation["parameters"] = params
        if method in ("post", "put", "patch"):
            operation["requestBody"] = {
                "required": False,
                "content": {
                    "application/json": {
                        "schema": {"type": "object"},
                    }
                },
            }
        if raw_path in DEPRECATED_PATHS:
            operation["deprecated"] = True
        if raw_path in PUBLIC_PATHS:
            operation["security"] = []

        paths.setdefault(norm_path, {})[method] = operation

    return {
        "openapi": "3.1.0",
        "info": {
            "title": "LLMOps Architecture Knowledge Hub API",
            "version": CONTRACT_VERSION,
            "description": (
                "Generated deterministically from the frozen contract shapes in tests/contract/frozen/. "
                "See docs/contracts/knowledge-hub-api-v1.md and docs/CLIENTS.md."
            ),
        },
        "servers": [
            {"url": "http://127.0.0.1:8000", "description": "Local LLMOps server"},
        ],
        "security": [{"bearerAuth": []}],
        "components": {
            "securitySchemes": {
                "bearerAuth": {
                    "type": "http",
                    "scheme": "bearer",
                }
            }
        },
        "paths": dict(sorted(paths.items())),
    }


def main() -> None:
    spec = build_openapi()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(spec, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote OpenAPI 3.1.0 schema ({len(spec['paths'])} paths) to {OUTPUT_PATH.relative_to(ROOT_DIR)}")


if __name__ == "__main__":
    main()
