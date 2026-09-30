"""``kb suggest-links``: LLM-assisted links from draft controls to the doctrine (OFFLINE ONLY).

This is the only place where a language model is used, in an offline CLI, never on a
served route. The model (``LLM_ENDPOINT`` + ``LLM_MODEL``, OpenAI-compatible API such as
Ollama's ``/v1/chat/completions``) proposes, for each draft control, the principles,
patterns and decisions that satisfy it and architecture acceptance criteria. Everything
it produces is marked ``links_production_mode: llm-derived`` and must go through the
expert review sheet. Without ``LLM_ENDPOINT`` the step is skipped.
"""

from __future__ import annotations

import json
import os
import re
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pipelines.kb_candidates.kb import join_frontmatter, load_assets, split_frontmatter

LINKABLE_TYPES = ("principle", "pattern", "decision")
PostJson = Callable[[str, dict[str, Any]], dict[str, Any]]

PROMPT = """You map a regulatory requirement to an architecture knowledge base.
Requirement {id} ({ref}):
\"\"\"{text}\"\"\"

Knowledge base assets (id: title):
{assets}

Answer with JSON only: {{"satisfied_by": [asset ids from the list that help satisfy the requirement],
"acceptance_criteria": [2 to 4 verifiable architecture acceptance criteria, one sentence each]}}.
Use only ids from the list; return an empty list when none applies."""


def _post_json(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        result: dict[str, Any] = json.loads(resp.read().decode("utf-8"))
        return result


def _first_json_object(text: str) -> dict[str, Any]:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return {}
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def suggest_links(
    staging: str | Path,
    kb_dir: str | Path = "data/kb",
    endpoint: str | None = None,
    model: str | None = None,
    post: PostJson | None = None,
) -> dict[str, Any]:
    endpoint = endpoint if endpoint is not None else os.getenv("LLM_ENDPOINT")
    if not endpoint:
        return {"skipped": True, "reason": "LLM_ENDPOINT is not set: link suggestion skipped", "updated": 0}
    model = model or os.getenv("LLM_MODEL", "llama3.1")
    post = post or _post_json
    url = endpoint.rstrip("/") + ("" if endpoint.rstrip("/").endswith("/chat/completions") else "/v1/chat/completions")
    assets = [a for a in load_assets(kb_dir) if a.type in LINKABLE_TYPES and a.frontmatter.get("status") == "active"]
    known = {a.id for a in assets}
    catalogue = "\n".join(f"- {a.id}: {a.title}" for a in sorted(assets, key=lambda a: a.id))

    updated = 0
    for draft in sorted(Path(staging).glob("*.md")):
        fm, body = split_frontmatter(draft.read_text(encoding="utf-8"))
        if fm is None:
            continue
        legal = re.search(r"## Legal Requirement\n(.*?)(?:\n## |\Z)", body, re.DOTALL)
        prompt = PROMPT.format(id=fm["id"], ref=fm.get("source_ref", ""), text=(legal.group(1) if legal else body).strip(),
                               assets=catalogue)
        response = post(url, {"model": model, "temperature": 0,
                              "messages": [{"role": "user", "content": prompt}]})
        content = ((response.get("choices") or [{}])[0].get("message") or {}).get("content", "")
        proposal = _first_json_object(str(content))
        links = [str(x) for x in proposal.get("satisfied_by") or [] if str(x) in known]
        criteria = [str(x).strip() for x in proposal.get("acceptance_criteria") or [] if str(x).strip()]
        fm["proposed_links"] = links
        fm["proposed_acceptance_criteria"] = criteria
        fm["links_production_mode"] = "llm-derived"
        fm["links_model"] = model
        draft.write_text(join_frontmatter(fm, body), encoding="utf-8")
        updated += 1
    return {"skipped": False, "updated": updated, "model": model}
