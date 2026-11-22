"""Hypothesis strategies for URL_Checker tests (Property 42)."""

from __future__ import annotations

from dataclasses import dataclass

from hypothesis import strategies as st

_label = st.text(alphabet="abcdefgh", min_size=3, max_size=8)
_RISKY = ["top", "xyz", "click", "icu", "cc", "vip", "shop", "online", "live", "buzz"]
_GOV = ["vneid", "bocongan", "dichvucong", "chinhphu", "csgt", "phatnguoi"]


@dataclass(frozen=True)
class UrlSample:
    text: str
    domain: str | None  # expected normalised host (None when IDNA decoding rewrites it)
    expected_flags: frozenset[str]


@st.composite
def urls_with_features(draw: st.DrawFn) -> UrlSample:
    """URL built from parts with deliberately injected features and the flags they imply."""
    flags: set[str] = set()
    scheme = draw(st.sampled_from(["http://", "https://"]))
    www = draw(st.booleans())
    sub = draw(st.one_of(st.just(""), _label.map(lambda s: s + ".")))
    label = draw(_label)
    kind = draw(st.sampled_from(["plain", "gov", "punycode"]))
    if kind == "gov":
        label = draw(st.sampled_from(_GOV)) + "-" + label
        flags.add("GOV_SPOOF")
    elif kind == "punycode":
        # Decoding may rewrite the host, so the exact domain is not asserted for this kind.
        label = "xn--" + label
        flags.add("PUNYCODE")
    tld = draw(st.sampled_from(_RISKY + ["com", "net", "vn"]))
    if tld in _RISKY:
        flags.add("RISKY_TLD")
    path = "/" + draw(_label)
    if draw(st.booleans()):
        path += ".apk"
        flags.add("APK_DOWNLOAD")
    host = f"{sub}{label}.{tld}"
    domain = None if kind == "punycode" else host
    shown = ("www." if www else "") + host
    if draw(st.booleans()):
        shown = shown.upper()
    defang = draw(st.booleans())
    if defang:
        shown = shown.replace(".", "[.]")
    return UrlSample(scheme + shown + path, domain, frozenset(flags))
