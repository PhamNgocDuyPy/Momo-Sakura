from guardian.tools.entity_scanner import scan_entities


def test_account_bank_amount_from_chat() -> None:
    e = scan_entities("Ck 2 lít vào STK 0071000999888 VCB nha, tiền cơm")
    assert [a.account_number for a in e.accounts] == ["0071000999888"]
    assert e.accounts[0].bank_bin == "970436"
    assert "970436" in e.bank_bins
    assert 2_000_000 not in e.amounts and 200_000 in e.amounts


def test_bank_alias_variants() -> None:
    e = scan_entities("chuyen Techcombank, stk 19036789012")
    assert e.accounts[0].bank_bin == "970407"
    assert scan_entities("MB 123456789012 tk").bank_bins == ("970422",)


def test_number_without_context_or_with_strong_pii_keyword_is_not_account() -> None:
    assert scan_entities("so 0912345678 goi nhe").accounts == ()
    assert scan_entities("cccd 079123456789").accounts == ()
    assert scan_entities("otp 123456").accounts == ()


def test_urls_and_empty_input() -> None:
    e = scan_entities("tai app tai hxxp://momo-vn[.]top/a.apk")
    assert e.urls and e.urls[0].is_hard
    assert scan_entities("") == scan_entities("   ")
