"""``kb extract-triggers``: candidate trigger rules from the "consequences" sections of the doctrine (K22, OFFLINE ONLY).

The patterns and the ADRs of the knowledge base already say, in natural language, what has to be decided next: their
"Consequences", "Trade-offs", "Implications", "When not to use this" and "Revisit when" sections. A language model reads them and
**proposes** rules (K19) in the facts vocabulary (K18). Like ``kb suggest-links`` this is the only place a model is used, in
an offline command, never on a served route. Everything it produces:

* is **constrained**: a rule is validated by the K19 validator; the passage it cites (``source_quote``) must appear verbatim in the
  section it was read from, otherwise it is dropped and reported;
* names a key the vocabulary does not know ⇒ the model must define it (``new_keys``): the key is submitted as a ``fact_key``
  candidate **to be reviewed**, and the rule fails its ``schema`` check (naming the key) until a person accepts, merges or amends;
* is ``llm-derived`` and a **candidate**: it enters the cycle of contract 1.2 and reaches the knowledge base only through human
  review, promotion and publication. Nothing is published here.

Without ``LLM_ENDPOINT`` the step is skipped. Replaying it creates nothing that already exists (a rule, a key, or a candidate in
flight with the same identifier).
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml

from pipelines import triggers
from pipelines.engagement import facts as fact_module
from pipelines.frameworks.links import _first_json_object, _post_json
from pipelines.kb_candidates import rules as rule_candidates
from pipelines.kb_candidates.kb import load_assets

SECTIONS = ("Consequences", "Trade-offs", "Implications", "When not to use this", "Revisit when", "Points d'attention", "Conséquences")
CARRIER_TYPES = ("principle", "pattern", "decision")
PostJson = Callable[[str, dict[str, Any]], dict[str, Any]]

PROMPT = """You turn the "{section}" section of an architecture knowledge element into trigger rules.
A rule says: when these facts are asserted about a programme, this question becomes relevant and must be decided.

Element {asset} ({title}), section "{section}":
\"\"\"{text}\"\"\"

Vocabulary of facts (key: type, permitted values, unit):
{vocabulary}

Answer with JSON only: {{"rules": [{{
  "slug": "short-kebab-case-name",
  "when": [{{"key": "<a vocabulary key>", "op": "eq|neq|gte|lte|in", "value": <value of the key's type>}}],
  "question": {{"fr": "...", "en": "..."}}, "rationale": {{"fr": "...", "en": "..."}},
  "initial_level": "L0_named or L1_framed", "suggested_role": "architect", "mandatory": false,
  "source_quote": "an exact sentence of the section that justifies the rule",
  "new_keys": [{{"key": "domain.name", "type": "int|bool|enum|duration", "values": ["only for an enum"],
                "unit": "optional", "label": {{"fr": "...", "en": "..."}}}}]
}}]}}.
Use only keys of the vocabulary; if a condition needs a key it does not have, define it in "new_keys".
Return {{"rules": []}} when the section states nothing that a stated fact would trigger."""


def _sections(body: str) -> dict[str, str]:
    parts = re.split(r"^## +(.+?)\s*$", body, flags=re.MULTILINE)
    return {parts[i].strip(): parts[i + 1].strip() for i in range(1, len(parts) - 1, 2)}


def _squash(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def _vocabulary_lines(vocabulary: dict[str, Any]) -> str:
    lines = []
    for key in sorted(vocabulary["keys"]):
        d = vocabulary["keys"][key]
        extra = f" {d['values']}" if d.get("values") else ""
        unit = f" ({d['unit']})" if d.get("unit") else ""
        lines.append(f"- {key}: {d['type']}{extra}{unit}")
    return "\n".join(lines)


def extract_triggers(
    kb_dir: str | Path,
    service: Any,
    asset_id: str | None = None,
    endpoint: str | None = None,
    model: str | None = None,
    post: PostJson | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Read the consequence sections, submit candidates. Returns a report; never publishes anything."""
    endpoint = endpoint if endpoint is not None else os.getenv("LLM_ENDPOINT")
    if not endpoint:
        return {"skipped": True, "reason": "LLM_ENDPOINT is not set: trigger extraction skipped", "submitted": []}
    model = model or os.getenv("LLM_MODEL", "llama3.1")
    post = post or _post_json
    url = endpoint.rstrip("/") + ("" if endpoint.rstrip("/").endswith("/chat/completions") else "/v1/chat/completions")
    kb = Path(kb_dir)
    vocabulary = fact_module.load(kb / "vocabulary" / "facts.yaml")
    existing_rules = {p.stem for p in (kb / triggers.TRIGGERS_DIR).glob("*.yaml")} if (kb / triggers.TRIGGERS_DIR).is_dir() else set()
    in_flight = [c for c in service.find() if c.get("asset_type") in rule_candidates.TRIGGER_TYPES and c["status"] not in ("rejected",)]
    taken_titles = {c["title"] for c in in_flight}
    report: dict[str, Any] = {"skipped": False, "model": model, "submitted": [], "key_candidates": [], "dropped": [], "unchanged": []}
    new_keys_seen: set[str] = set()

    assets = [a for a in load_assets(kb) if a.type in CARRIER_TYPES and a.frontmatter.get("status") == "active"
              and (asset_id is None or a.id == asset_id)]
    for asset in sorted(assets, key=lambda a: a.id):
        sections = _sections(asset.body)
        for name in SECTIONS:
            text = sections.get(name)
            if not text:
                continue
            prompt = PROMPT.format(section=name, asset=asset.id, title=asset.title, text=text, vocabulary=_vocabulary_lines(vocabulary))
            response = post(url, {"model": model, "temperature": 0, "messages": [{"role": "user", "content": prompt}]})
            content = ((response.get("choices") or [{}])[0].get("message") or {}).get("content", "")
            proposals = _first_json_object(str(content)).get("rules") or []
            for proposal in proposals if isinstance(proposals, list) else []:
                _handle(proposal, asset, name, text, vocabulary, kb, service, existing_rules, taken_titles, new_keys_seen, report, dry_run)
    return report


def _handle(proposal, asset, section, text, vocabulary, kb, service, existing_rules, taken_titles, new_keys_seen, report, dry_run) -> None:
    ref = {"asset": asset.id, "section": section}
    if not isinstance(proposal, dict):
        report["dropped"].append({**ref, "reason": "a rule must be a JSON object"})
        return
    quote = str(proposal.get("source_quote") or "")
    if not quote.strip() or _squash(quote) not in _squash(text):
        report["dropped"].append({**ref, "slug": proposal.get("slug"), "reason": "source_quote is not a passage of the section"})
        return
    name = rule_candidates.slug(str(proposal.get("slug") or ""))
    if not name or name.startswith("local-"):
        report["dropped"].append({**ref, "reason": "the rule needs a slug"})
        return
    trigger_id = f"TRG-{name}"
    title = f"Trigger {trigger_id}"
    if trigger_id in existing_rules or title in taken_titles:
        report["unchanged"].append({**ref, "trigger_id": trigger_id})
        return
    rule = {
        "trigger_id": trigger_id, "version": 1, "asset": asset.id, "when": proposal.get("when"),
        "question": proposal.get("question"), "rationale": proposal.get("rationale"),
        "initial_level": proposal.get("initial_level"), "suggested_role": proposal.get("suggested_role"),
        "mandatory": proposal.get("mandatory", False),
    }
    unknown = sorted({c["key"] for c in rule["when"] if isinstance(c, dict) and isinstance(c.get("key"), str)
                      and c["key"] not in vocabulary["keys"]}) if isinstance(rule["when"], list) else []
    defined = {k["key"]: k for k in proposal.get("new_keys") or [] if isinstance(k, dict) and isinstance(k.get("key"), str)}
    undefined = [k for k in unknown if k not in defined]
    if undefined:
        report["dropped"].append({**ref, "trigger_id": trigger_id, "reason": f"unknown key(s) {undefined} without a definition in new_keys"})
        return
    source = {"system": "kb-extraction", "production_mode": "llm-derived"}
    rationale = f"Source: {asset.id} § {section}: «{quote.strip()}»"
    if dry_run:
        report["submitted"].append({**ref, "trigger_id": trigger_id, "dry_run": True, "new_keys": unknown})
        return
    for key in unknown:  # a key the vocabulary lacks is proposed for review, never added
        key_title = f"Fact key {key}"
        if key in new_keys_seen or key_title in taken_titles:
            continue
        new_keys_seen.add(key)
        definition = {k: v for k, v in defined[key].items() if k != "asset"}
        cand = service.submit({
            "kind": "new_asset", "asset_type": "fact_key", "title": key_title, "proposed_content": yaml.safe_dump(definition, sort_keys=False, allow_unicode=True),
            "rationale": f"Needed by rule {trigger_id}. {rationale}", "source": source}, actor="kb-extraction")
        report["key_candidates"].append({"id": cand["id"], "key": key, "status": cand["status"]})
    domain = asset.frontmatter.get("domain")
    cand = service.submit({
        "kind": "new_asset", "asset_type": "trigger", "title": title, "domain": domain if isinstance(domain, list) else [],
        "proposed_content": yaml.safe_dump(rule, sort_keys=False, allow_unicode=True, width=1000, default_flow_style=None),
        "rationale": rationale + (f" Unknown key(s) {unknown}: proposed as fact_key candidate(s)." if unknown else ""),
        "source": source}, actor="kb-extraction")
    taken_titles.add(title)
    report["submitted"].append({**ref, "trigger_id": trigger_id, "candidate": cand["id"], "status": cand["status"], "new_keys": unknown})


def render(report: dict[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2)
