"""Property 16: Che PII đầy đủ và giữ số tài khoản.

**Validates: Requirements 10.1, 10.4, 10.5**
"""

from __future__ import annotations

from hypothesis import given

from guardian.tools.pii import detect_pii, redact_pii_local
from tests.property.strategies.pii import CONTACT_NAMES, account_with_context, vn_text_with_pii


# Feature: momo-guardian-web, Property 16: Che PII đầy đủ và giữ số tài khoản
@given(vn_text_with_pii())
def test_pii_fully_redacted(sample) -> None:
    redacted, _ = redact_pii_local(sample.text, CONTACT_NAMES)
    for value in sample.digit_values:
        assert value not in redacted
    for name in sample.names:
        assert name not in redacted
    assert detect_pii(redacted, contact_names=CONTACT_NAMES) == []


# Feature: momo-guardian-web, Property 16: Che PII đầy đủ và giữ số tài khoản
@given(account_with_context())
def test_account_number_with_context_preserved(case: tuple[str, str]) -> None:
    text, number = case
    redacted, _ = redact_pii_local(text, CONTACT_NAMES)
    assert number in redacted
