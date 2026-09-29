"""data/kb/owners.yaml is consistent with the knowledge base and data/kb/CODEOWNERS."""

import re
from pathlib import Path

from pipelines.kb_candidates.kb import load_assets
from pipelines.kb_candidates.owners import load_owners

KB = Path(__file__).parent.parent.parent / "data" / "kb"


def _domains_in_use() -> set[str]:
    domains: set[str] = set()
    for asset in load_assets(KB):
        value = asset.frontmatter.get("domain") or []
        domains.update(str(d) for d in (value if isinstance(value, list) else [value]))
    return domains


def test_every_domain_used_by_an_asset_has_an_owner():
    owners = load_owners(KB)
    orphans = sorted(
        d for d in _domains_in_use()
        if not any("/".join(d.split("/")[:i]) in owners.domains for i in range(len(d.split("/")), 0, -1))
    )
    assert not orphans, f"Domains without an owner in data/kb/owners.yaml: {orphans}"


def test_domain_owners_are_declared():
    owners = load_owners(KB)
    undeclared = sorted({h for h in owners.domains.values() if h not in owners.owners})
    assert not undeclared, f"Owners used in 'domains' but not declared in 'owners': {undeclared}"
    assert owners.default_owner in owners.owners


def test_codeowners_handles_are_declared():
    owners = load_owners(KB)
    handles = set(re.findall(r"@[\w.-]+", (KB / "CODEOWNERS").read_text(encoding="utf-8")))
    missing = sorted(h for h in handles if h not in owners.owners)
    assert not missing, f"CODEOWNERS handles missing from data/kb/owners.yaml: {missing}"
