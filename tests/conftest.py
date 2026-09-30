"""Root test configuration — keeps the working tree clean across a test session.

Some code paths exercised by the suite write into tracked locations:

* serving the engagement plane opens the committed demo database
  (``data/engagements/<id>.lbug``) through ``ElicitationRepository``, which runs the
  idempotent schema initializer and rewrites the file on close even when no data
  changes;
* the elicitation engine writes its mailbox cards, documents and reports under
  ``artifacts/<engagement>/`` and ``projects/<engagement>/`` relative to the
  working directory, and the scenario tests regenerate those artefacts.

Rather than altering these paths (frozen by the v1 contract), the test session
snapshots the tracked files in those locations and restores them byte-for-byte at
the end, and removes the untracked (non-ignored) files it created there, so that
``make test`` leaves ``git status`` clean. To regenerate the committed scenario
artefacts, run the scenario test directly and commit the result.
"""

import os
import subprocess
from collections.abc import Generator
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).parent.parent

# The code hard-codes no project: the reference demo engagement and blueprint are
# configured like in `make demo` (tests are allowed to name the demo project).
os.environ.setdefault("LLMOPS_ENGAGEMENT", "nordwave-mcx-2027")
os.environ.setdefault("LLMOPS_BLUEPRINT", "BLU-hla-mcx")

_GUARDED_PATHS = (
    "data/*.lbug",
    "data/engagements",
    "data/snapshots",
    "artifacts",
    "projects",
)


def _git_ls(*args: str) -> set[str]:
    try:
        out = subprocess.check_output(
            ["git", "ls-files", *args, "--", *_GUARDED_PATHS],
            cwd=str(ROOT_DIR),
            stderr=subprocess.DEVNULL,
        ).decode("utf-8")
    except Exception:
        return set()
    return {line for line in out.splitlines() if line.strip()}


@pytest.fixture(scope="session", autouse=True)
def _preserve_working_tree() -> Generator[None, None, None]:
    tracked = _git_ls()
    saved = {rel: (ROOT_DIR / rel).read_bytes() for rel in tracked if (ROOT_DIR / rel).is_file()}
    untracked_before = _git_ls("--others", "--exclude-standard")
    yield
    from tools.adapters.ladybug_store import LadybugGraphStore

    # Release open handles first so the database is not flushed again after restore.
    LadybugGraphStore.clear_cache()
    for rel, content in saved.items():
        path = ROOT_DIR / rel
        if not path.is_file() or path.read_bytes() != content:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
    for rel in _git_ls("--others", "--exclude-standard") - untracked_before:
        (ROOT_DIR / rel).unlink(missing_ok=True)


@pytest.fixture(scope="session", autouse=True)
def _isolated_candidate_queue(tmp_path_factory: pytest.TempPathFactory) -> Generator[None, None, None]:
    """KB candidates created by tests (e.g. through suggestions) go to a temporary queue."""
    previous = os.environ.get("CANDIDATES_DIR")
    os.environ["CANDIDATES_DIR"] = str(tmp_path_factory.mktemp("candidates"))
    yield
    if previous is None:
        os.environ.pop("CANDIDATES_DIR", None)
    else:
        os.environ["CANDIDATES_DIR"] = previous


@pytest.fixture
def scripted_interpretation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Declare a scripted interpretation (tests/fixtures/elicitation/) for engagements.

    Usage: ``scripted_interpretation("my-engagement")`` — the answers of that engagement
    then become candidate statements, as a reference scenario would script them.
    """
    import shutil

    examples = tmp_path / "examples"
    monkeypatch.setenv("LLMOPS_EXAMPLES_DIR", str(examples))
    script = ROOT_DIR / "tests" / "fixtures" / "elicitation" / "verbatim_statement_script.yaml"

    def declare(*engagements: str) -> Path:
        for engagement in engagements:
            target = examples / engagement
            target.mkdir(parents=True, exist_ok=True)
            shutil.copy(script, target / "scripted_interpretations.yaml")
        return examples

    return declare
