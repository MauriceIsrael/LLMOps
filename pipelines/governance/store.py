"""SQL storage of the governance state (plan governance, lot L5, decision D1).

SQLAlchemy Core over SQLite (development, demo) or PostgreSQL (production). The URL comes
from ``GOVERNANCE_DATABASE_URL``; with ``CANDIDATES_BACKEND=sql`` and no URL, a SQLite file
``data/governance.db`` (ignored by git) is used. A ``postgresql://`` URL needs the
``postgres`` extra (``psycopg``).

Tables are created on first use (``metadata.create_all``); later lots add their own tables
to the same ``metadata``. There is no migration tool yet: a schema change ships with an
explicit ``ALTER`` in ``_upgrade``.
"""

from __future__ import annotations

import os
import threading

from sqlalchemy import (
    Boolean,
    Column,
    Engine,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
)
from sqlalchemy.exc import IntegrityError

metadata = MetaData()

candidates = Table(
    "candidates", metadata,
    Column("id", String(24), primary_key=True),
    Column("status", String(32), nullable=False, index=True),
    Column("source_system", String(64)),
    Column("engagement", String(128)),
    Column("assigned_owner", String(128), index=True),
    Column("doc", Text, nullable=False),
    Column("updated_at", String(32), nullable=False),
)

domain_owners = Table(
    "domain_owners", metadata,
    Column("handle", String(128), primary_key=True),
    Column("email", String(256), unique=True),
    Column("discord_webhook", Text),
    Column("ntfy_topic", String(128)),
    Column("roles", Text, nullable=False, default="[]"),
    Column("delegated", Boolean, nullable=False, default=False),
)

owner_domains = Table(
    "owner_domains", metadata,
    Column("domain", String(256), primary_key=True),
    Column("handle", String(128), nullable=False),
)

review_requests = Table(
    "review_requests", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("candidate_id", String(24), nullable=False, index=True),
    Column("requested_handle", String(128), nullable=False, index=True),
    Column("kind", String(16), nullable=False),  # second_review | advice
    Column("message", Text),
    Column("requested_by", String(128), nullable=False),
    Column("due_at", String(32), nullable=False),
    Column("status", String(16), nullable=False, default="open"),  # open | done | cancelled
    Column("created_at", String(32), nullable=False),
    Column("closed_at", String(32)),
)

comments = Table(
    "comments", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("candidate_id", String(24), nullable=False, index=True),
    Column("author", String(256), nullable=False),
    Column("body", Text, nullable=False),
    Column("at", String(32), nullable=False),
)

governance_events = Table(
    "governance_events", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("at", String(32), nullable=False),
    Column("type", String(48), nullable=False, index=True),
    Column("candidate_id", String(24), index=True),
    Column("actor", String(256), nullable=False),
    Column("recipients", Text, nullable=False, default="[]"),
    Column("payload", Text, nullable=False, default="{}"),
)

eval_datasets = Table(
    "eval_datasets", metadata,
    Column("name", String(64), primary_key=True),
    Column("description", Text),
    Column("created_at", String(32), nullable=False),
)

eval_cases = Table(
    "eval_cases", metadata,
    Column("dataset", String(64), primary_key=True),
    Column("case_id", String(64), primary_key=True),
    Column("doc", Text, nullable=False),
    Column("annotation_status", String(16), nullable=False),  # proposed | validated | rejected
    Column("annotated_by", String(128)),
    Column("annotated_at", String(32)),
)

eval_runs = Table(
    "eval_runs", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("dataset", String(64), nullable=False, index=True),
    Column("at", String(32), nullable=False),
    Column("run_by", String(256), nullable=False),
    Column("metrics", Text, nullable=False),
)

verdict_feedback = Table(
    "verdict_feedback", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("at", String(32), nullable=False),
    Column("reporter", String(256), nullable=False),
    Column("typed_id", String(128), nullable=False, index=True),
    Column("check_id", String(128)),
    Column("feedback", String(24), nullable=False),  # wrong_violation | missed_violation | correct
    Column("justification", Text, nullable=False),
    Column("context", Text, nullable=False),  # JSON: option, subject, frameworks
    Column("status", String(16), nullable=False, default="open"),  # open | converted | dismissed
    Column("converted_to", String(128)),
)

framework_ingestions = Table(
    "framework_ingestions", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("framework", String(64), nullable=False, index=True),
    Column("version", String(64), nullable=False),
    Column("tag", String(64)),
    Column("source_name", String(256), nullable=False),
    Column("source_sha256", String(64), nullable=False),
    Column("status", String(24), nullable=False),  # reviewing | applied | partially_applied
    Column("created_by", String(128), nullable=False),
    Column("created_at", String(32), nullable=False),
    Column("declaration_reset", Boolean, nullable=False, default=False),
)

ingestion_rows = Table(
    "ingestion_rows", metadata,
    Column("ingestion_id", Integer, primary_key=True),
    Column("requirement_id", String(128), primary_key=True),
    Column("position", Integer, nullable=False),
    Column("doc", Text, nullable=False),  # JSON: draft text, proposals, decision, result
)

embeddings = Table(
    "embeddings", metadata,
    Column("ref", String(128), primary_key=True),
    Column("model_id", String(128), primary_key=True),
    Column("kind", String(16), nullable=False),
    Column("model_version", String(64), nullable=False),
    Column("dim", Integer, nullable=False),
    Column("vector", Text, nullable=False),  # JSON array of floats
    Column("text_sha256", String(64), nullable=False),
    Column("language", String(8)),
    Column("created_by", String(256), nullable=False),
    Column("created_at", String(32), nullable=False),
)

reuse_confirmations = Table(
    "reuse_confirmations", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("at", String(32), nullable=False),
    Column("actor", String(256), nullable=False),
    Column("subject_fingerprint", String(64), nullable=False, index=True),
    Column("subject_label", String(200), nullable=False),
    Column("matched_ref", String(128), nullable=False, index=True),
    Column("assumptions_digest", String(64), nullable=False),
    Column("model", String(128)),
    Column("scores", Text, nullable=False),  # JSON
    Column("assumptions", Text, nullable=False),  # JSON: [{text, status, note}]
    Column("outcome", String(32), nullable=False, index=True),
    Column("comment", Text),
)

# Engagement access (K14, ADR-KH-01 A11). An engagement with a row here is *managed*: it is closed to everyone but its
# members, in every environment. Handles only identify people outside this table; e-mails never leave it.
engagement_registry = Table(
    "engagement_registry", metadata,
    Column("engagement", String(64), primary_key=True),
    Column("confidentiality", String(16), nullable=False),
    Column("created_at", String(32), nullable=False),
    Column("created_by", String(256), nullable=False),
)

engagement_members = Table(
    "engagement_members", metadata,
    Column("engagement", String(64), primary_key=True),
    Column("email", String(256), primary_key=True),
    Column("handle", String(64), nullable=False),
    Column("role", String(16), nullable=False),
    Column("added_by", String(256), nullable=False),
    Column("added_at", String(32), nullable=False),
)

engagement_audit = Table(
    "engagement_audit", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("at", String(32), nullable=False),
    Column("engagement", String(64), nullable=False, index=True),
    Column("actor", String(256), nullable=False),
    Column("action", String(16), nullable=False),
    Column("outcome", String(16), nullable=False),  # allowed | denied
    Column("detail", Text, nullable=False, default="{}"),
)

# Sealed engagement snapshots (K11): content-addressed, immutable, resolvable later. ``snapshot_id`` derives from the checksum,
# so the same state gives the same identifier and an issued identifier never designates other content.
engagement_exports = Table(
    "engagement_exports", metadata,
    Column("snapshot_id", String(128), primary_key=True),
    Column("engagement", String(64), nullable=False, index=True),
    Column("checksum", String(80), nullable=False),
    Column("produced_at", String(32), nullable=False),
    Column("produced_by", String(256), nullable=False),
    Column("is_provisional", Boolean, nullable=False),
    Column("envelope", Text, nullable=False),  # canonical JSON of the whole envelope, as issued
)

counters = Table(
    "counters", metadata,
    Column("key", String(128), primary_key=True),
    Column("n", Integer, nullable=False),
)

governance_meta = Table(
    "governance_meta", metadata,
    Column("key", String(128), primary_key=True),
    Column("value", Text, nullable=False),
)

_engines: dict[str, Engine] = {}
_lock = threading.Lock()


def database_url() -> str | None:
    """Configured URL, the SQLite default when ``CANDIDATES_BACKEND=sql``, else ``None``."""
    url = os.getenv("GOVERNANCE_DATABASE_URL", "").strip()
    if not url and os.getenv("CANDIDATES_BACKEND", "file").strip().lower() == "sql":
        url = "sqlite:///data/governance.db"
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url or None


def get_engine(url: str | None = None) -> Engine:
    """Engine for ``url`` (default: the configured one); tables are created once per URL."""
    url = url or database_url()
    if not url:
        raise RuntimeError("No governance database: set GOVERNANCE_DATABASE_URL or CANDIDATES_BACKEND=sql.")
    with _lock:
        engine = _engines.get(url)
        if engine is None:
            if url.startswith("sqlite:///") and url != "sqlite:///:memory:":
                path = url[len("sqlite:///"):]
                if os.path.dirname(path):
                    os.makedirs(os.path.dirname(path), exist_ok=True)
            engine = create_engine(url, future=True)
            metadata.create_all(engine)
            _engines[url] = engine
        return engine


def dispose_engines() -> None:
    """Close every cached engine (tests, reconfiguration)."""
    with _lock:
        for engine in _engines.values():
            engine.dispose()
        _engines.clear()


def next_counter(engine: Engine, key: str) -> int:
    """Atomically incremented counter (the UPDATE takes the row lock, so it is portable)."""
    with engine.begin() as conn:
        try:
            with conn.begin_nested():
                conn.execute(counters.insert().values(key=key, n=0))
        except IntegrityError:
            pass
        conn.execute(counters.update().where(counters.c.key == key).values(n=counters.c.n + 1))
        return int(conn.execute(counters.select().where(counters.c.key == key)).one().n)
