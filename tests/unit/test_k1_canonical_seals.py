"""K1 (ADR-KH-01 D6): every seal a suite component may verify follows the canonical-json v1 profile."""

import ast
import json
from pathlib import Path

import pytest

from pipelines import canonical

ROOT = Path(__file__).resolve().parents[2]
SEALED_KEYS = ("applicability_index", "assets", "glossary", "frameworks", "controls", "compliance_index")
SCANNED = ("mcp_server", "pipelines", "scripts", "tools")
# Functions allowed to serialise JSON and hash in the same body: they hash a *file or text* for provenance or ETag, not a
# snapshot seal. Keep this list short and justified.
ALLOWED = {
    "pipelines/bundle/verify.py": {"payload_sha256"},  # delegates to pipelines.canonical
    # internal fingerprint of judged assumptions: not a seal, and changing it would outdate every stored judgement
    "pipelines/similarity/reuse.py": {"assumptions_digest"},
    # writes the envelope file and hashes each asset's *text* for provenance; the snapshot seal itself is canonical.sha256
    "scripts/export_sealed_snapshot.py": {"export_sealed_snapshot"},
}


def test_committed_sealed_snapshot_carries_a_canonical_checksum():
    for path in ("fixtures/sealed_snapshot.json", "data/snapshots/latest.json"):
        data = json.loads((ROOT / path).read_text(encoding="utf-8"))
        payload = {k: data.get(k, [] if k in ("frameworks", "controls") else {}) for k in SEALED_KEYS}
        assert data["payload_sha256"] == canonical.sha256(payload), path


def test_export_refuses_what_the_profile_refuses():
    for bad in (float("nan"), float("inf"), 2**53, {"d": {1, 2}}):
        with pytest.raises(canonical.CanonicalError):
            canonical.sha256({"assets": [bad]})


def _calls(node: ast.AST) -> set[str]:
    names = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call):
            f = sub.func
            names.add(f"{f.value.id}.{f.attr}" if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) else getattr(f, "id", getattr(f, "attr", "")))
    return names


def _offenders() -> list[str]:
    found = []
    for top in SCANNED:
        for path in sorted((ROOT / top).rglob("*.py")):
            rel = path.relative_to(ROOT).as_posix()
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for fn in ast.walk(tree):
                if not isinstance(fn, ast.FunctionDef | ast.AsyncFunctionDef):
                    continue
                calls = _calls(fn)
                if "json.dumps" in calls and ({"hashlib.sha256", "compute_sha256", "hashlib.md5"} & calls):
                    if fn.name not in ALLOWED.get(rel, set()):
                        found.append(f"{rel}:{fn.name}")
    return sorted(found)


def test_no_seal_is_computed_from_a_json_dump_outside_the_canonical_module():
    assert _offenders() == [], (
        "These functions serialise JSON and hash it in the same body. A seal that a suite component verifies must use "
        "pipelines.canonical (json.dumps differs on 7 of 40 shared vectors and accepts the 8 to refuse)."
    )


def test_the_snapshot_seal_is_computed_by_the_canonical_module():
    source = (ROOT / "scripts/export_sealed_snapshot.py").read_text(encoding="utf-8")
    assert "canonical.sha256(payload_data)" in source
    assert "json.dumps(payload_data" not in source
    compliance = (ROOT / "pipelines/compliance_mapper.py").read_text(encoding="utf-8")
    assert "canonical.sha256(data)" in compliance
