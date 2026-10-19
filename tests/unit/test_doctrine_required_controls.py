"""Issue #106 — the controls of the required frameworks are never cut by ``max_items`` or by the character budget.

Synthetic doctrine only (no graph, no project data).
"""

import pytest

from pipelines.doctrine.context import build_doctrine_context
from pipelines.doctrine.index import DoctrineIndex
from tests.unit.test_check_option import _entry, _vocab

REQUIRED = 30


@pytest.fixture
def big_index() -> DoctrineIndex:
    entries = [
        _entry(f"FW1-{i:02d}", "control", f"Control number {i}",
               f"## Legal Requirement\nRequirement {i} " + "of the framework " * 30, framework="FW1")
        for i in range(1, REQUIRED + 1)
    ]
    entries += [
        _entry(f"P-{200 + i}", "principle", f"Principle {i} about remediation",
               "## Statement\nEvery closed loop remediation needs a human approval.", domain=["network-automation"])
        for i in range(8)
    ]
    return DoctrineIndex(entries=entries, vocabulary=_vocab())


def _required(ctx):
    return [i for i in ctx["items"] if i["required"]]


@pytest.mark.parametrize("max_items", [1, 5, 20, 120])
def test_every_required_control_is_returned_whatever_max_items(big_index, max_items):
    ctx = build_doctrine_context(big_index, "closed loop remediation", frameworks=["FW1"], max_items=max_items,
                                 max_chars=100000)
    assert len(_required(ctx)) == REQUIRED
    assert ctx["required_total"] == REQUIRED
    assert ctx["omitted_required"] == []


def test_max_items_only_caps_the_doctrine_that_is_not_required(big_index):
    ctx = build_doctrine_context(big_index, "closed loop remediation", frameworks=["FW1"], max_items=3,
                                 max_chars=100000)
    assert len([i for i in ctx["items"] if not i["required"]]) == 3
    assert ctx["truncated"] is True  # five principles were left out: the flag still says so


def test_a_tight_character_budget_shortens_required_excerpts_but_drops_none(big_index):
    ctx = build_doctrine_context(big_index, "closed loop remediation", frameworks=["FW1"], max_items=20,
                                 max_chars=400)
    assert len(_required(ctx)) == REQUIRED and ctx["omitted_required"] == []
    assert ctx["truncated"] is True
    assert sum(len(i["excerpt"]) for i in ctx["items"]) <= 400  # the budget holds: the excerpts give way, not the controls
    assert all(i["excerpt"] for i in _required(ctx))


def test_a_budget_smaller_than_the_number_of_controls_still_lists_them_all(big_index):
    ctx = build_doctrine_context(big_index, "closed loop remediation", frameworks=["FW1"], max_items=20, max_chars=20)
    assert len(_required(ctx)) == REQUIRED and ctx["omitted_required"] == []
    assert sum(len(i["excerpt"]) for i in ctx["items"]) <= 20 and ctx["truncated"] is True


def test_without_a_required_framework_the_package_is_unchanged(big_index):
    ctx = build_doctrine_context(big_index, "closed loop remediation", max_items=3, max_chars=100000)
    assert ctx["required_total"] == 0 and ctx["omitted_required"] == []
    assert len(ctx["items"]) <= 3
