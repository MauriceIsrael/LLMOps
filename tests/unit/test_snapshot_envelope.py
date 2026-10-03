"""K2: ``is_provisional`` is derived from its reasons, never declared."""

import pytest

from pipelines.snapshot_envelope import channel_envelope, provisional

CHECKSUM = "sha256:" + "0" * 64


def test_ripe_and_conflict_free_is_not_provisional():
    assert provisional(0, 0) == {"is_provisional": False, "provisional_reasons": {"unripe_subjects": 0, "open_conflicts": 0}}


@pytest.mark.parametrize(("unripe", "conflicts"), [(1, 0), (0, 1), (3, 2)])
def test_one_unripe_subject_or_one_open_conflict_makes_the_whole_snapshot_provisional(unripe, conflicts):
    out = provisional(unripe, conflicts)
    assert out["is_provisional"] is True
    assert out["provisional_reasons"] == {"unripe_subjects": unripe, "open_conflicts": conflicts}


@pytest.mark.parametrize("bad", [-1, 1.5, "2", None, True])
def test_reasons_must_be_counts(bad):
    with pytest.raises(ValueError):
        provisional(bad, 0)


def test_channel_envelope_fields():
    env = channel_envelope(CHECKSUM, open_conflicts=2)
    assert env["emitter"] == "knowledge-hub" and env["checksum"] == CHECKSUM and env["rebuiltByEmitterTest"] is True
    assert env["regenerate"].startswith("poetry run python ") and env["is_provisional"] is True
