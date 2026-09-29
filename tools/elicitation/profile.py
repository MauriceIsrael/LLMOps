"""Engagement profiles: engagement-specific settings kept out of the code.

The engine is generic. Anything that belongs to one engagement (default subject and
role, vocabulary shown on question cards, harvest candidates, instruction plan roster,
scripted interpretations, canvas templates) is read from data files in the engagement's
example directory: ``$LLMOPS_EXAMPLES_DIR/<engagement>/`` (default ``examples/``), e.g.
``examples/<engagement>/engagement_profile.yaml``. Without a profile, generic defaults
apply.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

PROFILE_FILE = "engagement_profile.yaml"
GENERIC_PROJECTED_SEQUENCE = [
    "1. Frame the root subjects of the blueprint (L1_framed)",
    "2. Decompose the framed subjects into their parts (L2_decomposed)",
    "3. Decide the parameters of the decomposed subjects (L3_decided)",
    "4. Specify the remaining parameters and finalise section readiness (L4_specified)",
]


def examples_dir() -> Path:
    return Path(os.getenv("LLMOPS_EXAMPLES_DIR", "examples"))


def engagement_dir(engagement: str | None) -> Path | None:
    """Directory holding the engagement's example data, if it exists."""
    if not engagement:
        return None
    path = examples_dir() / engagement
    return path if path.is_dir() else None


def engagement_file(engagement: str | None, name: str) -> Path | None:
    directory = engagement_dir(engagement)
    if directory is None:
        return None
    path = directory / name
    return path if path.is_file() else None


@dataclass
class EngagementProfile:
    default_subject: str = ""
    default_role: str = "architect"
    decomposition_route: str = "architect"
    mailbox_terms: list[str] = field(default_factory=list)
    harvest_candidates: list[dict[str, Any]] = field(default_factory=list)
    roster: dict[str, str] = field(default_factory=dict)
    projected_sequence: list[str] = field(default_factory=lambda: list(GENERIC_PROJECTED_SEQUENCE))


def load_profile(engagement: str | None) -> EngagementProfile:
    path = engagement_file(engagement, PROFILE_FILE)
    if path is None:
        return EngagementProfile()
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    profile = EngagementProfile()
    for key in ("default_subject", "default_role", "decomposition_route"):
        if data.get(key):
            setattr(profile, key, str(data[key]))
    if isinstance(data.get("mailbox_terms"), list):
        profile.mailbox_terms = [str(t) for t in data["mailbox_terms"]]
    if isinstance(data.get("harvest_candidates"), list):
        profile.harvest_candidates = [dict(c) for c in data["harvest_candidates"]]
    if isinstance(data.get("roster"), dict):
        profile.roster = {str(k): str(v) for k, v in data["roster"].items()}
    if isinstance(data.get("projected_sequence"), list):
        profile.projected_sequence = [str(s) for s in data["projected_sequence"]]
    return profile
