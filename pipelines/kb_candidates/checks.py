"""Automatic, deterministic checks run on every KB candidate.

Each check returns ``{"name", "status": pass|fail|warn, "detail"}``. A single ``fail``
blocks the candidate (``checks_failed``); warnings must be handled by the reviewer.

1. ``schema``            front matter and sections follow the type's template and the
                         front matter schema (``data/kb/schema/``);
2. ``references``        every cited asset (related, implements_controls, supersedes,
                         requires, typed ids) exists in the KB;
3. ``duplicate``         title or content too close to an existing asset (warn);
4. ``anonymization``     no client/site name (denylist), IP address or CIDR (fail);
                         identifying volumes (warn);
5. ``doctrine_conflict`` the content violates a doctrine check clause (warn);
6. ``llm_unreviewed``    ``production_mode: llm-derived`` (warn);
7. ``previously_rejected`` identical to a rejected candidate (warn).
"""

from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pipelines.doctrine.checks import validate_clause
from pipelines.doctrine.text import content_tokens, normalize, normalize_phrase
from pipelines.kb_candidates.kb import KbAsset, load_assets, split_frontmatter

DEFAULT_DUPLICATE_THRESHOLD = 0.6
TITLE_DUPLICATE_THRESHOLD = 0.8

# Sections expected per type (from data/kb/*/_template.md and existing assets); missing -> warn.
EXPECTED_SECTIONS = {
    "principle": ["Statement", "How to verify"],
    "pattern": ["Problem", "Solution", "Trade-offs", "When not to use this"],
    "decision": ["Context", "Options considered", "Decision", "Consequences"],
    "control": ["Legal Requirement", "Architecture Acceptance Criteria"],
}
CONTROL_REQUIRED_FIELDS = ("id", "title", "type", "framework", "version", "severity")
PROMOTION_FIELDS = ("status", "confidence", "owner", "last_reviewed")
CONTROL_ID = re.compile(r"^[A-Z0-9]+(?:-[A-Za-z0-9]+)+$")
GLOSSARY_ENTRY = re.compile(r"^\*\*(.+?)\*\*\s*[—\-]\s*\S", re.MULTILINE)
TYPED_ID = re.compile(r"\b(principle|pattern|decision|control):([A-Za-z0-9][A-Za-z0-9._-]*[A-Za-z0-9])")
BARE_ID = re.compile(r"\b(ADR-\d{4}|P-\d{3}|PAT-\d{3})\b")
REFERENCE_FIELDS = ("related", "implements_controls", "supersedes", "requires", "satisfied_by")

# An address may end a sentence ("... is 10.0.0.1."): only a following digit (or ".digit") excludes it.
IPV4 = re.compile(r"(?<![\d.])(\d{1,3}(?:\.\d{1,3}){3})(/\d{1,2})?(?!\d|\.\d)")
IPV6 = re.compile(r"(?<![0-9A-Fa-f:])((?:[0-9A-Fa-f]{0,4}:){2,7}[0-9A-Fa-f]{0,4})(/\d{1,3})?(?![0-9A-Fa-f:])")
VOLUME = re.compile(
    r"\b\d[\d\s.,]{2,}\s*(?:k|m)?\s*(?:subscribers|abonnes|abonnés|users|utilisateurs|terminals|terminaux|"
    r"sites|agents|customers|clients|lines|lignes|radios)\b",
    re.IGNORECASE,
)
DOCUMENTATION_NETWORKS = [
    ipaddress.ip_network(n)
    for n in ("192.0.2.0/24", "198.51.100.0/24", "203.0.113.0/24", "2001:db8::/32")
]


@dataclass
class CheckContext:
    """What the checks need to know about the knowledge base."""

    kb_dir: Path
    assets: list[KbAsset]
    known_domains: set[str]
    denylist: list[str]
    rejected_fingerprints: dict[str, str] = field(default_factory=dict)
    doctrine_index_loader: Callable[[], Any] | None = None
    duplicate_threshold: float = DEFAULT_DUPLICATE_THRESHOLD

    @property
    def ids(self) -> set[str]:
        return {a.id for a in self.assets}

    def asset(self, asset_id: str) -> KbAsset | None:
        return next((a for a in self.assets if a.id == asset_id), None)


def _result(name: str, status: str, detail: str) -> dict[str, str]:
    return {"name": name, "status": status, "detail": detail}


def load_denylist(kb_dir: str | Path) -> list[str]:
    path = Path(kb_dir) / "anonymization_denylist.txt"
    if not path.is_file():
        return []
    terms = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            terms.append(line)
    return terms


def load_known_domains(kb_dir: str | Path) -> set[str]:
    """Domain vocabulary: front matter schema enum + domains declared in owners.yaml."""
    import yaml

    kb = Path(kb_dir)
    domains: set[str] = set()
    schema_path = kb / "schema" / "frontmatter.schema.json"
    if schema_path.is_file():
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        domains |= set(schema.get("properties", {}).get("domain", {}).get("items", {}).get("enum", []))
    owners_path = kb / "owners.yaml"
    if owners_path.is_file():
        owners = yaml.safe_load(owners_path.read_text(encoding="utf-8")) or {}
        domains |= set((owners.get("domains") or {}).keys())
    return domains


def fingerprint(candidate: dict[str, Any]) -> str:
    text = normalize(candidate.get("title", "")) + "|" + normalize(candidate.get("proposed_content", ""))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_context(
    kb_dir: str | Path,
    rejected: list[dict[str, Any]] | None = None,
    doctrine_index_loader: Callable[[], Any] | None = None,
) -> CheckContext:
    kb = Path(kb_dir)
    threshold = float(os.getenv("KB_DUPLICATE_THRESHOLD", DEFAULT_DUPLICATE_THRESHOLD))
    return CheckContext(
        kb_dir=kb,
        assets=load_assets(kb),
        known_domains=load_known_domains(kb),
        denylist=load_denylist(kb),
        rejected_fingerprints={fingerprint(c): c["id"] for c in rejected or []},
        doctrine_index_loader=doctrine_index_loader,
        duplicate_threshold=threshold,
    )


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------

def _sections(body: str) -> list[str]:
    return [line[3:].strip() for line in body.splitlines() if line.startswith("## ")]


def _as_list(value: Any) -> list[str]:
    if value in (None, ""):
        return []
    if isinstance(value, list):
        return [str(v) for v in value]
    return [str(value)]


def _schema_problems(fm: dict[str, Any], asset_type: str, ctx: CheckContext) -> list[str]:
    problems: list[str] = []
    if asset_type == "control":
        problems += [f"missing '{k}'" for k in CONTROL_REQUIRED_FIELDS if not fm.get(k)]
        if fm.get("id") and not CONTROL_ID.match(str(fm["id"])):
            problems.append(f"control id '{fm['id']}' does not match {CONTROL_ID.pattern}")
    else:
        schema_path = ctx.kb_dir / "schema" / "frontmatter.schema.json"
        if schema_path.is_file():
            try:
                import jsonschema
            except ImportError:  # pragma: no cover - jsonschema ships with the dev environment
                jsonschema = None
            if jsonschema is not None:
                schema = json.loads(schema_path.read_text(encoding="utf-8"))
                # The domain vocabulary is checked below (schema enum + owners.yaml). Lifecycle
                # fields are set at promotion (status, computed confidence, owner, review date).
                schema.get("properties", {}).pop("domain", None)
                schema["required"] = [r for r in schema.get("required", []) if r not in PROMOTION_FIELDS]
                validator = jsonschema.Draft202012Validator(schema)
                for err in sorted(validator.iter_errors(fm), key=lambda e: list(e.path)):
                    where = ".".join(str(p) for p in err.path) or "front matter"
                    problems.append(f"{where}: {err.message}")
    if fm.get("type") and fm.get("type") != asset_type:
        problems.append(f"front matter type '{fm.get('type')}' differs from asset_type '{asset_type}'")
    unknown = [d for d in _as_list(fm.get("domain")) if ctx.known_domains and d not in ctx.known_domains]
    if unknown:
        problems.append(f"unknown domain(s) {unknown}: declare them in data/kb/owners.yaml and the domain vocabulary")
    for i, clause in enumerate(fm.get("checks") or []):
        for p in validate_clause(clause):
            problems.append(f"checks[{i}]: {p}")
    return problems


def check_schema(candidate: dict[str, Any], ctx: CheckContext) -> dict[str, str]:
    asset_type = candidate.get("asset_type")
    content = candidate.get("proposed_content", "")
    if asset_type == "glossary":
        if GLOSSARY_ENTRY.search(content):
            return _result("schema", "pass", "glossary entry format '**Term** — definition'")
        return _result("schema", "fail", "glossary content must contain '**Term** — definition' entries")
    fm, body = split_frontmatter(content)
    if fm is None:
        if candidate.get("kind") == "rex":
            return _result("schema", "warn",
                           "free-form return of experience: the reviewer must amend it into an asset "
                           "(front matter + template sections) before promotion")
        return _result("schema", "fail", "missing or invalid YAML front matter")
    asset_type = asset_type or str(fm.get("type") or "")
    if asset_type not in EXPECTED_SECTIONS:
        return _result("schema", "fail", f"unknown asset type '{asset_type}'")
    problems = _schema_problems(fm, asset_type, ctx)
    asset_id = str(fm.get("id") or "")
    # An amendment, or a framework ingestion of an existing control, updates its target in place.
    if candidate.get("kind") == "amendment" or candidate.get("target_asset_id"):
        target = candidate.get("target_asset_id")
        if asset_id != target:
            problems.append(f"amendment front matter id '{asset_id}' differs from target_asset_id '{target}'")
        if target not in ctx.ids:
            problems.append(f"target asset '{target}' does not exist")
    elif asset_id in ctx.ids:
        problems.append(f"id '{asset_id}' already exists: submit an amendment with target_asset_id '{asset_id}'")
    if problems:
        return _result("schema", "fail", "; ".join(problems))
    missing = [s for s in EXPECTED_SECTIONS[asset_type] if s not in _sections(body)]
    if missing:
        return _result("schema", "warn", f"missing template sections: {missing}")
    if asset_type == "decision" and not _as_list(fm.get("assumptions")):
        return _result("schema", "warn", "no 'assumptions' documented: without the hypotheses under which this decision "
                       "holds, nobody can tell whether it applies to another subject (plan similarity, D8)")
    return _result("schema", "pass", f"{asset_type} front matter and sections are valid")


def check_references(candidate: dict[str, Any], ctx: CheckContext) -> dict[str, str]:
    content = candidate.get("proposed_content", "")
    fm, body = split_frontmatter(content)
    own_id = str((fm or {}).get("id") or candidate.get("target_asset_id") or "")
    cited: set[str] = set()
    for key in REFERENCE_FIELDS:
        cited.update(_as_list((fm or {}).get(key)))
    cited.update(m.group(2) for m in TYPED_ID.finditer(body))
    cited.update(m.group(1) for m in BARE_ID.finditer(body))
    cited.discard(own_id)
    if candidate.get("target_asset_id"):
        cited.add(candidate["target_asset_id"])
    missing = sorted(c for c in cited if c not in ctx.ids)
    if missing:
        return _result("references", "fail", f"unknown references: {missing}")
    return _result("references", "pass", f"{len(cited)} reference(s) resolved")


def _jaccard(a: set[str], b: set[str]) -> float:
    return len(a & b) / len(a | b) if a and b else 0.0


def check_duplicate(candidate: dict[str, Any], ctx: CheckContext) -> dict[str, str]:
    fm, body = split_frontmatter(candidate.get("proposed_content", ""))
    own = {str((fm or {}).get("id") or ""), str(candidate.get("target_asset_id") or "")}
    title_tokens = set(content_tokens(candidate.get("title", "")))
    body_tokens = set(content_tokens(body))
    best: tuple[float, str, str] = (0.0, "", "")
    for asset in ctx.assets:
        if asset.id in own:
            continue
        t = _jaccard(title_tokens, set(content_tokens(asset.title)))
        b = _jaccard(body_tokens, set(content_tokens(asset.body)))
        if t >= TITLE_DUPLICATE_THRESHOLD and t > best[0]:
            best = (t, asset.id, "title")
        if b >= ctx.duplicate_threshold and b > best[0]:
            best = (b, asset.id, "content")
    if best[1]:
        return _result(
            "duplicate", "warn",
            f"{best[2]} too close to {best[1]} (similarity {best[0]:.2f}): consider kind 'amendment' "
            f"with target_asset_id '{best[1]}'",
        )
    return _result("duplicate", "pass", "no close existing asset")


def _is_documentation_ip(addr: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return any(addr in net for net in DOCUMENTATION_NETWORKS if net.version == addr.version)


def find_ip_addresses(text: str) -> list[str]:
    found: list[str] = []
    for match in IPV4.finditer(text):
        try:
            addr4 = ipaddress.IPv4Address(match.group(1))
        except ValueError:
            continue
        if not _is_documentation_ip(addr4):
            found.append(match.group(0))
    for match in IPV6.finditer(text):
        candidate = match.group(1)
        if candidate.count(":") < 2 or not re.search(r"[0-9A-Fa-f]", candidate):
            continue
        try:
            addr6 = ipaddress.IPv6Address(candidate)
        except ValueError:
            continue
        if not _is_documentation_ip(addr6):
            found.append(match.group(0))
    return found


def check_anonymization(candidate: dict[str, Any], ctx: CheckContext) -> dict[str, str]:
    text = "\n".join(
        str(candidate.get(k) or "") for k in ("title", "rationale", "proposed_content")
    )
    norm = normalize(text)
    names = sorted({t for t in ctx.denylist if normalize_phrase(t) and f" {normalize_phrase(t)} " in norm})
    ips = find_ip_addresses(text)
    problems = []
    if names:
        problems.append(f"denylisted name(s): {names}")
    if ips:
        problems.append(f"IP address(es)/CIDR: {sorted(set(ips))}")
    if problems:
        return _result("anonymization", "fail", "; ".join(problems) + " — generalize before submitting")
    volumes = [m.group(0).strip() for m in VOLUME.finditer(text)]
    if volumes:
        return _result("anonymization", "warn", f"possibly identifying figures: {volumes[:5]}")
    return _result("anonymization", "pass", "no identifying data detected")


def check_doctrine_conflict(candidate: dict[str, Any], ctx: CheckContext) -> dict[str, str]:
    if ctx.doctrine_index_loader is None:
        return _result("doctrine_conflict", "warn", "doctrine index unavailable: conflict check skipped")
    try:
        index = ctx.doctrine_index_loader()
    except Exception as exc:  # pragma: no cover - depends on the deployment
        return _result("doctrine_conflict", "warn", f"doctrine index unavailable: {exc}")
    from pipelines.doctrine.judge import check_option

    fm, body = split_frontmatter(candidate.get("proposed_content", ""))
    excluded = {str((fm or {}).get("id") or ""), str(candidate.get("target_asset_id") or "")}
    excluded.update(_as_list((fm or {}).get("supersedes")))
    result = check_option(index, {"title": candidate.get("title", ""), "description": body})
    violations = [
        f"{v['typed_id']} ({v['check_id']})"
        for v in result["verdicts"]
        if v["verdict"] == "violates" and v["typed_id"].split(":", 1)[1] not in excluded
    ]
    if violations:
        return _result(
            "doctrine_conflict", "warn",
            f"violates {violations}: the review must supersede them or record a motivated exception",
        )
    return _result("doctrine_conflict", "pass", "no doctrine check clause violated")


def check_llm_unreviewed(candidate: dict[str, Any], ctx: CheckContext) -> dict[str, str]:
    if (candidate.get("source") or {}).get("production_mode") == "llm-derived":
        return _result("llm_unreviewed", "warn", "llm-derived content: not publishable without human review")
    return _result("llm_unreviewed", "pass", "human-authored or human-approved content")


def check_previously_rejected(candidate: dict[str, Any], ctx: CheckContext) -> dict[str, str]:
    rejected = ctx.rejected_fingerprints.get(fingerprint(candidate))
    if rejected and rejected != candidate.get("id"):
        return _result("previously_rejected", "warn", f"identical to rejected candidate {rejected}")
    return _result("previously_rejected", "pass", "not previously rejected")


CHECKS = (
    check_schema,
    check_references,
    check_duplicate,
    check_anonymization,
    check_doctrine_conflict,
    check_llm_unreviewed,
    check_previously_rejected,
)


def run_checks(candidate: dict[str, Any], ctx: CheckContext) -> list[dict[str, str]]:
    return [check(candidate, ctx) for check in CHECKS]


def has_failure(checks: list[dict[str, str]]) -> bool:
    return any(c["status"] == "fail" for c in checks)
