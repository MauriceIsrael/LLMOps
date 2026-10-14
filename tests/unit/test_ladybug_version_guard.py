"""The graph engine in use is the one the project was verified with.

``ladybug`` 0.21.0 broke ``MATCH (n {id: …}) OPTIONAL MATCH …``: the anchor row comes back with NULL columns when the optional
part matches nothing, silently, and ``get_compliance_matrix`` crashes on it. ``pyproject.toml`` therefore bounds the engine
(``< 0.21``); an environment built with ``pip install ladybug`` ignores that bound and gets the broken engine. This test says so
plainly, instead of leaving the symptoms (a NULL where a value was written) to be investigated one at a time.
See docs/TESTING.md.
"""

import tomllib
from importlib import metadata
from pathlib import Path

from packaging.specifiers import SpecifierSet
from packaging.version import Version

ROOT = Path(__file__).resolve().parents[2]


def test_the_installed_graph_engine_is_inside_the_range_the_project_declares():
    declared = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["tool"]["poetry"]["dependencies"]["ladybug"]
    installed = Version(metadata.version("ladybug"))
    assert installed in SpecifierSet(declared), (
        f"ladybug {installed} is installed but pyproject.toml declares '{declared}'. Rebuild the environment from the lock "
        "(`poetry install`, or the Docker test image): ladybug >= 0.21 returns NULL for the anchor row of an OPTIONAL MATCH. "
        "See docs/TESTING.md."
    )
