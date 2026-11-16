"""Normalized RequirementRef triplet for strict RFP requirement cross-referencing (LLMOps #150).

A suite document designates a requirement by ``RequirementRef {sourceId, requirementKey, version}``
(``contracts/requirement-ref.md``, ADR-SUITE-04 §3):

* **Three fields or nothing** ("une référence partielle n'existe jamais"): a requirement without a
  known ``version`` (or missing ``sourceId`` / ``requirementKey``) must never emit a partial ``ref``.
* ``sourceId`` follows the normative pattern ``^[a-z0-9-]+:[a-z0-9-]+$`` (the authoritative registry,
  never an instance URL), e.g. ``knowledge-hub:<engagement>`` or ``tuleap:<project>``.
* ``version`` changes whenever a requirement is modified so downstream consumers (conformity-engine,
  Document Engine) can detect stale allocations and perform strict joins on ``(sourceId, requirementKey)``.
"""

from __future__ import annotations

import re
from typing import Any

SOURCE_ID_PATTERN = re.compile(r"^[a-z0-9-]+:[a-z0-9-]+$")
HUB_SOURCE_PREFIX = "knowledge-hub"
_NON_SLUG = re.compile(r"[^a-z0-9-]+")
_REQUIRED_KEYS = frozenset({"sourceId", "requirementKey", "version"})


class RequirementRefError(ValueError):
    """Raised when a RequirementRef is partial or violates the suite contract."""

    def __init__(self, reason: str, message: str) -> None:
        self.reason = reason
        super().__init__(message)


def normalize_slug(value: str) -> str:
    """Normalize an identifier into a lowercase ``[a-z0-9-]+`` slug."""
    return _NON_SLUG.sub("-", (value or "").lower()).strip("-")


def hub_source_id(scope: str) -> str:
    """Build a normative ``knowledge-hub:<scope>`` sourceId for Hub-owned requirements."""
    slug = normalize_slug(scope)
    if not slug:
        raise RequirementRefError("invalid_source_id", f"cannot derive a valid sourceId slug from {scope!r}")
    candidate = f"{HUB_SOURCE_PREFIX}:{slug}"
    if not SOURCE_ID_PATTERN.match(candidate):
        raise RequirementRefError("invalid_source_id", f"derived sourceId {candidate!r} does not match ^[a-z0-9-]+:[a-z0-9-]+$")
    return candidate


def requirement_ref(source_id: str, requirement_key: str, version: str | int) -> dict[str, str]:
    """Construct a validated ``RequirementRef {sourceId, requirementKey, version}`` triplet."""
    if not isinstance(source_id, str) or not SOURCE_ID_PATTERN.match(source_id):
        raise RequirementRefError(
            "invalid_source_id",
            f"sourceId must match ^[a-z0-9-]+:[a-z0-9-]+$, got {source_id!r}",
        )
    if not isinstance(requirement_key, str) or not requirement_key.strip():
        raise RequirementRefError(
            "missing_requirement_key",
            f"requirementKey must be a non-empty string, got {requirement_key!r}",
        )
    if isinstance(version, bool) or version is None:
        raise RequirementRefError("missing_version", f"version must be a non-empty string or positive integer, got {version!r}")
    if isinstance(version, int):
        if version < 1:
            raise RequirementRefError("invalid_version", f"numeric version must be >= 1, got {version!r}")
        version_str = str(version)
    elif isinstance(version, str):
        version_str = version.strip()
        if not version_str:
            raise RequirementRefError("missing_version", "version must be a non-empty string")
    else:
        raise RequirementRefError("invalid_version", f"version must be a string or integer, got {type(version).__name__}")

    return {
        "sourceId": source_id,
        "requirementKey": requirement_key.strip(),
        "version": version_str,
    }


def validate_requirement_ref(raw: Any) -> dict[str, str]:
    """Strictly validate an incoming ``RequirementRef`` object (all three fields required, no extras)."""
    if not isinstance(raw, dict):
        raise RequirementRefError("invalid_ref", "RequirementRef must be an object with sourceId, requirementKey and version")
    keys = set(raw.keys())
    missing = sorted(_REQUIRED_KEYS - keys)
    if missing:
        raise RequirementRefError(
            "partial_ref",
            f"a partial RequirementRef does not exist (missing: {', '.join(missing)})",
        )
    extra = sorted(keys - _REQUIRED_KEYS)
    if extra:
        raise RequirementRefError(
            "invalid_ref",
            f"unexpected fields in RequirementRef: {', '.join(extra)}",
        )
    return requirement_ref(raw["sourceId"], raw["requirementKey"], raw["version"])


def try_requirement_ref(source_id: Any, requirement_key: Any, version: Any) -> dict[str, str] | None:
    """Return a valid ``RequirementRef`` or ``None`` if any field is absent/invalid (never emits a partial ref)."""
    if not isinstance(source_id, str) or not source_id.strip():
        return None
    if not isinstance(requirement_key, str) or not requirement_key.strip():
        return None
    if isinstance(version, bool) or version is None:
        return None
    if isinstance(version, str) and not version.strip():
        return None
    try:
        return requirement_ref(source_id, requirement_key, version)
    except RequirementRefError:
        return None


def bump_requirement_version(current_version: str | int | None) -> str:
    """Return the next version string when a requirement's content is modified."""
    if current_version is None or isinstance(current_version, bool):
        return "1"
    s = str(current_version).strip()
    if not s:
        return "1"
    if s.isdigit():
        return str(int(s) + 1)
    if s.startswith("v") and s[1:].isdigit():
        return f"v{int(s[1:]) + 1}"
    return f"{s}.1"
