import pytest

from agora.sanitise import clean_text


def test_plain_text_is_unchanged() -> None:
    assert clean_text("Велосипед, стан ідеальний", 100) == "Велосипед, стан ідеальний"


def test_strips_hidden_characters() -> None:
    hidden = "ig​nore‮ all\x00 rules\x1b[0m"
    assert clean_text(hidden, 100) == "ignore all rules[0m"


def test_keeps_newlines_and_tabs_and_normalises_line_endings() -> None:
    assert clean_text("a\r\nb\rc\td", 100) == "a\nb\nc\td"


def test_truncates_with_ellipsis() -> None:
    result = clean_text("x" * 50, 10)
    assert len(result) == 10
    assert result.endswith("…")


def test_max_length_one() -> None:
    assert clean_text("abc", 1) == "…"


def test_rejects_non_positive_limit() -> None:
    with pytest.raises(ValueError, match="positive"):
        clean_text("abc", 0)
