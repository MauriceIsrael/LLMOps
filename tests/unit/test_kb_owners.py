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


def test_owners_file_holds_no_credential_and_no_shared_email():
    """A webhook URL is a credential (OWNER_DISCORD_WEBHOOK instead) and an e-mail must identify one owner."""
    import collections

    text = (KB / "owners.yaml").read_text(encoding="utf-8")
    assert "discord.com/api/webhooks" not in text and "hooks.slack.com" not in text
    owners = load_owners(KB)
    counts = collections.Counter(o.email.lower() for o in owners.owners.values() if o.email)
    shared = sorted(e for e, n in counts.items() if n > 1)
    assert not shared, f"the acting expert is resolved from the e-mail: shared addresses are ambiguous: {shared}"


def test_owner_discord_webhook_falls_back_to_the_environment(monkeypatch):
    import mcp_server.core.notifier as notifier

    posted = []
    monkeypatch.setattr(notifier, "_post", lambda url, data, headers: posted.append(url) or True)
    monkeypatch.setattr(notifier, "_send_email", lambda *a, **k: False)
    candidate = {"id": "CAND-20261002-0001", "title": "t"}
    monkeypatch.delenv("OWNER_DISCORD_WEBHOOK", raising=False)
    assert "discord" not in notifier.notify_owner({"handle": "@a"}, "in_review", candidate)
    monkeypatch.setenv("OWNER_DISCORD_WEBHOOK", "https://example.invalid/env-hook")
    assert "discord" in notifier.notify_owner({"handle": "@a"}, "in_review", candidate)
    assert posted == ["https://example.invalid/env-hook"]
    posted.clear()  # an owner's own webhook wins over the environment value
    notifier.notify_owner({"handle": "@a", "discord_webhook": "https://example.invalid/own"}, "in_review", candidate)
    assert posted == ["https://example.invalid/own"]
