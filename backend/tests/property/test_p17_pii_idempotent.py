"""Property 17: Che PII idempotent.

**Validates: Requirements 10.3**
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from guardian.tools.pii import Tokenizer, redact_pii_local
from tests.property.strategies.pii import (
    CONTACT_NAMES,
    PiiSample,
    account_with_context,
    vn_text_with_pii,
)

_digit_heavy = st.text(alphabet="0123456789 .+-:[]_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdeotpstk", max_size=80)
_any_text = st.one_of(st.text(max_size=80), _digit_heavy)


def _assert_idempotent(text: str, names: tuple[str, ...] | None) -> None:
    once, _ = redact_pii_local(text, names)
    twice, counts = redact_pii_local(once, names)
    assert twice == once
    assert counts == {}


@settings(max_examples=200, deadline=None)
@given(vn_text_with_pii(), st.booleans())
def test_redact_is_idempotent_on_pii_text(sample: PiiSample, use_contacts: bool) -> None:
    _assert_idempotent(sample.text, CONTACT_NAMES if use_contacts else None)


@settings(max_examples=200, deadline=None)
@given(_any_text, st.booleans())
def test_redact_is_idempotent_on_arbitrary_text(text: str, use_contacts: bool) -> None:
    _assert_idempotent(text, CONTACT_NAMES if use_contacts else None)


@settings(max_examples=100, deadline=None)
@given(account_with_context())
def test_redact_is_idempotent_on_account_context(sample: tuple[str, str]) -> None:
    _assert_idempotent(sample[0], CONTACT_NAMES)


@settings(max_examples=100, deadline=None)
@given(vn_text_with_pii())
def test_tokenizer_reuse_is_idempotent(sample: PiiSample) -> None:
    tokenizer = Tokenizer()
    once, _ = redact_pii_local(sample.text, CONTACT_NAMES, tokenizer)
    twice, _ = redact_pii_local(once, CONTACT_NAMES, tokenizer)
    assert twice == once
