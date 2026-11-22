import unicodedata

from guardian.control_plane.grounding import ground_string, is_grounded

TEXT = "Chuyển  khoản\n tiền   cọc iPhone [CCCD_1] mã MOMOXMAS26"


def test_substring_after_whitespace_normalization() -> None:
    assert ground_string("tiền cọc iPhone", TEXT) == "tiền cọc iPhone"
    assert ground_string("  Chuyển khoản ", TEXT) == "Chuyển khoản"


def test_nfc_equivalence() -> None:
    decomposed = unicodedata.normalize("NFD", "tiền cọc")
    assert is_grounded(decomposed, TEXT)


def test_not_substring_rejected() -> None:
    assert ground_string("tiền thuê nhà", TEXT) is None
    assert ground_string("momoxmas26", TEXT) is None


def test_forbidden_chars_rejected() -> None:
    assert ground_string("iPhone [CCCD_1]", TEXT) is None
    for ch in "[]<>":
        assert ground_string(ch, f"a {ch} b") is None


def test_empty_and_none() -> None:
    assert ground_string(None, TEXT) is None
    assert ground_string("   ", TEXT) is None
