"""The negation window stops at the end of the sentence (issue #88)."""

from pipelines.doctrine.text import contains_affirmed, normalize


def test_a_cue_does_not_negate_the_next_sentence():
    assert contains_affirmed(normalize("There is no budget. Human approval is required."), "human approval")
    assert contains_affirmed(normalize("No exception;\nhuman approval applies"), "human approval")


def test_a_cue_still_negates_within_its_sentence():
    assert not contains_affirmed(normalize("Deployed without human approval."), "human approval")


def test_decimal_points_do_not_split_sentences():
    assert contains_affirmed(normalize("Availability of 99.9 percent"), "99 9 percent")