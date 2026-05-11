from wigs.decision_labels import CANONICAL_DECISIONS, to_display_label


def test_canonical_decisions_are_underscore_enums():
    assert CANONICAL_DECISIONS == ("AVOID", "WATCH", "STRONG_WATCH", "STRONG_CANDIDATE")


def test_to_display_label_formats_strong_values():
    assert to_display_label("STRONG_WATCH") == "STRONG WATCH"
    assert to_display_label("STRONG_CANDIDATE") == "STRONG CANDIDATE"
