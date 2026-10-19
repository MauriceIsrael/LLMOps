"""Which files of the knowledge base the ingestion reads, and the fingerprint of one file.

One definition for the ingestion (``ingest``) and for the consistency check (``kb check``, issue #85): they must look at
the same files, or the check would answer another question than the one the ingestion answered.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

# Prose that is not an asset: never ingested.
NOT_ASSETS = ("README.md", "CONTRIBUTING.md", "GOVERNANCE.md", "deltas.md")


def kb_source_files(kb_dir: Path | str) -> list[Path]:
    """The Markdown and YAML files of ``kb_dir`` that the ingestion reads, sorted."""
    kb = Path(kb_dir)
    return sorted(
        p
        for p in [*kb.rglob("*.md"), *kb.rglob("*.yaml"), *kb.rglob("*.yml")]
        if not p.name.startswith("_") and p.name not in NOT_ASSETS
    )


def file_digest(text: str) -> str:
    """SHA-256 of a whole file (front matter included, where the check clauses live), independent of the line endings.

    A file read on Windows (``\\r\\n``) and on Linux (``\\n``) has the same digest: the graph is built on one machine and
    checked on another."""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
