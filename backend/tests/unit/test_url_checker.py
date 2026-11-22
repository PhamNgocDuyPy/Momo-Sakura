from __future__ import annotations

import asyncio

import httpx

from guardian.schemas.trace import TraceRecorder
from guardian.tools.url_checker import (
    SafeBrowsingClient,
    check_urls,
    check_urls_with_safe_browsing,
)


def _flags(text: str) -> set[str]:
    return {f for r in check_urls(text) for f in r.flags}


def test_defanged_apk_gov_spoof() -> None:
    (r,) = check_urls("Tải ngay: HTTPS://WWW.VneID-gov[.]top/app/vneid.apk")
    assert r.domain == "vneid-gov.top"
    assert {"APK_DOWNLOAD", "GOV_SPOOF", "RISKY_TLD"} <= r.flags
    assert r.is_hard


def test_official_and_gov_vn_not_flagged() -> None:
    assert _flags("https://www.momo.vn/uu-dai và https://dichvucong.gov.vn/") == set()


def test_brand_lookalike_shortener_ip_punycode() -> None:
    assert "BRAND_LOOKALIKE" in _flags("momo-khuyenmai.com")
    assert "SHORTENER" in _flags("bit.ly/abc")
    assert "IP_LITERAL" in _flags("http://192.168.1.5/x")
    assert "PUNYCODE" in _flags("https://xn--mmo-6qa.com")


def test_prose_and_email_not_urls() -> None:
    assert check_urls("file.txt và a@b.com, giá 1.5 triệu") == []


def test_safe_browsing_disabled_without_key() -> None:
    client = SafeBrowsingClient("")
    assert not client.enabled
    res = asyncio.run(check_urls_with_safe_browsing("https://a.com/x", client))
    assert "SAFE_BROWSING_HIT" not in res[0].flags


def test_safe_browsing_error_traces_and_hit_merges() -> None:
    def fail(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("boom")

    def hit(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"matches": [{"threat": {"url": "https://a.com/x"}}]})

    async def run(handler: httpx.MockTransport, trace: TraceRecorder):  # type: ignore[no-untyped-def]
        async with httpx.AsyncClient(transport=handler) as http:
            return await check_urls_with_safe_browsing(
                "https://a.com/x", SafeBrowsingClient("k", http), trace
            )

    t1 = TraceRecorder()
    res = asyncio.run(run(httpx.MockTransport(fail), t1))
    assert "SAFE_BROWSING_HIT" not in res[0].flags
    assert t1.has("safe_browsing", "error")
    res = asyncio.run(run(httpx.MockTransport(hit), TraceRecorder()))
    assert "SAFE_BROWSING_HIT" in res[0].flags
