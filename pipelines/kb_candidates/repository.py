"""Persistent storage of KB candidates.

Backends (``CANDIDATES_BACKEND``):

* ``file`` (default): one JSON document per candidate in ``CANDIDATES_DIR``
  (default ``data/candidates/``, ignored by git). Survives restarts on a persistent
  disk. **On Cloud Run the container file system is ephemeral**: mount a volume
  (e.g. a Cloud Storage FUSE or Filestore volume) at ``CANDIDATES_DIR``, or use the
  ``gcs`` backend.
* ``gcs``: Google Cloud Storage bucket (``CANDIDATES_GCS_BUCKET``) — not implemented yet.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pipelines.kb_candidates.model import CandidateNotFoundError

_ID_PATTERN = re.compile(r"^CAND-\d{8}-\d{4}$")


class CandidateRepository(ABC):
    """Storage interface for KB candidates."""

    @abstractmethod
    def next_id(self) -> str: ...

    @abstractmethod
    def save(self, candidate: dict[str, Any]) -> None: ...

    @abstractmethod
    def get(self, candidate_id: str) -> dict[str, Any]: ...

    @abstractmethod
    def all(self) -> list[dict[str, Any]]: ...

    def find(
        self,
        status: str | None = None,
        source: str | None = None,
        domain: str | None = None,
        engagement: str | None = None,
    ) -> list[dict[str, Any]]:
        """Candidates matching all given filters, newest first."""
        result = []
        for c in self.all():
            if status and c.get("status") != status:
                continue
            if source and (c.get("source") or {}).get("system") != source:
                continue
            if engagement and (c.get("source") or {}).get("engagement") != engagement:
                continue
            if domain and not any(d == domain or d.startswith(domain.rstrip("/") + "/") for d in c.get("domain") or []):
                continue
            result.append(c)
        return sorted(result, key=lambda c: c["id"], reverse=True)


class FileCandidateRepository(CandidateRepository):
    """One JSON file per candidate; writes are atomic (temporary file + rename)."""

    def __init__(self, base_dir: str | Path = "data/candidates") -> None:
        self.base_dir = Path(base_dir)

    def _path(self, candidate_id: str) -> Path:
        if not _ID_PATTERN.match(candidate_id):
            raise CandidateNotFoundError(candidate_id)
        return self.base_dir / f"{candidate_id}.json"

    def next_id(self) -> str:
        day = datetime.now(UTC).strftime("%Y%m%d")
        prefix = f"CAND-{day}-"
        existing = [p.stem for p in self.base_dir.glob(f"{prefix}*.json")] if self.base_dir.exists() else []
        seq = max((int(s[len(prefix):]) for s in existing if s[len(prefix):].isdigit()), default=0) + 1
        return f"{prefix}{seq:04d}"

    def save(self, candidate: dict[str, Any]) -> None:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        target = self._path(candidate["id"])
        fd, tmp = tempfile.mkstemp(dir=self.base_dir, prefix=".tmp-", suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(candidate, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        os.replace(tmp, target)

    def get(self, candidate_id: str) -> dict[str, Any]:
        path = self._path(candidate_id)
        if not path.is_file():
            raise CandidateNotFoundError(candidate_id)
        data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        return data

    def all(self) -> list[dict[str, Any]]:
        if not self.base_dir.exists():
            return []
        return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(self.base_dir.glob("CAND-*.json"))]


class GcsCandidateRepository(CandidateRepository):
    """Cloud Storage backend (production on Cloud Run).

    TODO(L2): implement with google-cloud-storage — one object per candidate under
    ``gs://$CANDIDATES_GCS_BUCKET/candidates/<id>.json``, generation-match
    preconditions for atomic updates, and a daily counter object for ``next_id``.
    """

    def __init__(self, bucket: str | None = None) -> None:
        self.bucket = bucket or os.getenv("CANDIDATES_GCS_BUCKET")

    def _unavailable(self) -> NotImplementedError:
        return NotImplementedError(
            "CANDIDATES_BACKEND=gcs is not implemented yet; use CANDIDATES_BACKEND=file with a persistent "
            "volume mounted at CANDIDATES_DIR (see docs/deployment.md)."
        )

    def next_id(self) -> str:
        raise self._unavailable()

    def save(self, candidate: dict[str, Any]) -> None:
        raise self._unavailable()

    def get(self, candidate_id: str) -> dict[str, Any]:
        raise self._unavailable()

    def all(self) -> list[dict[str, Any]]:
        raise self._unavailable()


def get_repository() -> CandidateRepository:
    """Repository configured by ``CANDIDATES_BACKEND`` / ``CANDIDATES_DIR`` (read at call time)."""
    backend = os.getenv("CANDIDATES_BACKEND", "file").strip().lower()
    if backend == "gcs":
        return GcsCandidateRepository()
    if backend != "file":
        raise ValueError(f"Unknown CANDIDATES_BACKEND '{backend}' (expected 'file' or 'gcs').")
    return FileCandidateRepository(os.getenv("CANDIDATES_DIR", "data/candidates"))
