"""Channel envelope of the Hub's sealed snapshots (K2, ADR-KH-01 D7).

The suite's channel registry (``contracts/channel-registry``) admits a channel when its emitter is named, its content carries
a SHA-256 checksum at the ``canonical-json v1`` profile, the emitter's own freshness test **rebuilds** the golden file
(``rebuiltByEmitterTest``) and the regeneration command is declared. The two-stage epistemics of ``CONTRATS_KH`` adds
``is_provisional`` and its reasons to the snapshot as a whole.

These fields are additive: the snapshot keeps its snake_case envelope (``snapshot_id``, ``payload_sha256``...).
"""

from __future__ import annotations

from typing import Any

EMITTER = "knowledge-hub"
REGENERATE_COMMAND = "poetry run python scripts/export_fixtures.py"


def provisional(unripe_subjects: int = 0, open_conflicts: int = 0) -> dict[str, Any]:
    """``is_provisional`` and its reasons, **derived** from the counts, never declared.

    A snapshot is provisional when a subject is below ``L3_decided`` or a conflict is open. The knowledge plane holds neither
    subjects nor conflicts, so its snapshot always reports zero; the engagement snapshot (K11) passes the real counts.
    """
    for name, value in (("unripe_subjects", unripe_subjects), ("open_conflicts", open_conflicts)):
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ValueError(f"{name} must be a non-negative integer, got {value!r}")
    return {
        "is_provisional": bool(unripe_subjects or open_conflicts),
        "provisional_reasons": {"unripe_subjects": unripe_subjects, "open_conflicts": open_conflicts},
    }


def channel_envelope(checksum: str, unripe_subjects: int = 0, open_conflicts: int = 0) -> dict[str, Any]:
    """The channel fields to add to a snapshot whose content is sealed by ``checksum`` (``sha256:<hex>``)."""
    return {
        "emitter": EMITTER,
        "checksum": checksum,
        "rebuiltByEmitterTest": True,
        "regenerate": REGENERATE_COMMAND,
        **provisional(unripe_subjects, open_conflicts),
    }
