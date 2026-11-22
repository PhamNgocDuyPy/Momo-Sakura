"""URL_Checker: deterministic URL extraction, normalisation and heuristic flags.

Pure heuristics (no network). ``SafeBrowsingClient`` is the only networked part and
only runs when ``GOOGLE_SAFE_BROWSING_API_KEY`` is configured.
"""

from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass, field
from urllib.parse import parse_qs, urlsplit

import httpx

from guardian.schemas.trace import TraceRecorder
from guardian.tools.banks import load_banks

APK_DOWNLOAD = "APK_DOWNLOAD"
GOV_SPOOF = "GOV_SPOOF"
BRAND_LOOKALIKE = "BRAND_LOOKALIKE"
RISKY_TLD = "RISKY_TLD"
PUNYCODE = "PUNYCODE"
IP_LITERAL = "IP_LITERAL"
SHORTENER = "SHORTENER"
SAFE_BROWSING_HIT = "SAFE_BROWSING_HIT"

HARD_FLAGS = frozenset({APK_DOWNLOAD, GOV_SPOOF})

GOV_TOKENS = ("vneid", "bocongan", "dichvucong", "chinhphu", "gov", "csgt", "phatnguoi", "thue")
BRAND_TOKENS = ("momo", "vietcombank", "shopee", "lazada", "tiki", "zalopay")
RISKY_TLDS = frozenset({"top", "xyz", "click", "icu", "cc", "vip", "shop", "online", "live", "buzz"})
SHORTENER_DOMAINS = frozenset({"bit.ly", "tinyurl.com", "t.ly", "cutt.ly"})

# Brand domains not covered by banks.json (promos fixture carries no domains).
_EXTRA_OFFICIAL_DOMAINS = (
    "momo.vn",
    "shopee.vn",
    "shopee.com",
    "lazada.vn",
    "lazada.com",
    "tiki.vn",
    "zalopay.vn",
)

# Small fixed TLD list used for registrable-domain extraction and bare-domain detection.
_TWO_LEVEL_SUFFIXES = frozenset(
    {"com.vn", "gov.vn", "edu.vn", "net.vn", "org.vn", "ac.vn", "info.vn", "co.uk"}
)
_KNOWN_TLDS = frozenset(
    {"vn", "com", "net", "org", "info", "io", "me", "co", "app", "dev", "link", "site", "store"}
    | RISKY_TLDS
)

_LABEL = r"(?:[^\W_](?:[\w-]*[^\W_])?)"
_HOST = rf"(?:{_LABEL}\.)+{_LABEL}"
_URL_RE = re.compile(
    rf"(?P<scheme>https?://)?(?P<host>{_HOST})(?::\d{{1,5}})?(?P<rest>[/?#][^\s<>\"']*)?",
    re.IGNORECASE,
)
_TRAILING_PUNCT = ".,;:!?)]}\"'"


@dataclass(frozen=True)
class UrlCheckResult:
    url: str  # refanged URL as it appeared in the text
    domain: str  # normalised host: lower-case, IDNA-decoded, no leading "www."
    registrable_domain: str
    flags: frozenset[str] = field(default_factory=frozenset)

    @property
    def is_hard(self) -> bool:
        return bool(self.flags & HARD_FLAGS)


def refang(text: str) -> str:
    """Undo common defanging: ``[.]``, ``(.)``, ``hxxp``."""
    out = re.sub(r"\s*[\[(]\s*\.\s*[\])]\s*", ".", text)
    return re.sub(r"\bhxxp(s?)(?=://|\[?:)", r"http\1", out, flags=re.IGNORECASE)


def _to_unicode_host(host: str) -> str:
    labels = []
    for label in host.split("."):
        if label.startswith("xn--"):
            try:
                label = label.encode("ascii").decode("idna")
            except (UnicodeError, ValueError):
                pass
        labels.append(label)
    return ".".join(labels)


def _to_ascii_host(host: str) -> str:
    try:
        return host.encode("idna").decode("ascii")
    except (UnicodeError, ValueError):
        return host


def normalize_host(host: str) -> str:
    host = host.strip().strip(".").lower()
    if host.startswith("www."):
        host = host[4:]
    return _to_unicode_host(host)


def registrable_domain(host: str) -> str:
    labels = host.split(".")
    if len(labels) <= 2:
        return host
    if ".".join(labels[-2:]) in _TWO_LEVEL_SUFFIXES:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])


def _is_ip(host: str) -> bool:
    try:
        ipaddress.IPv4Address(host)
    except ValueError:
        return False
    return True


def _official_domains() -> frozenset[str]:
    domains = set(_EXTRA_OFFICIAL_DOMAINS)
    try:
        for bank in load_banks():
            domains.update(d.lower() for d in bank.official_domains)
    except RuntimeError:
        pass
    return frozenset(domains)


def _is_official(host: str, official: frozenset[str]) -> bool:
    return any(host == d or host.endswith("." + d) for d in official)


def _accept_candidate(has_scheme: bool, host: str) -> bool:
    if has_scheme or _is_ip(host):
        return True
    tld = host.rsplit(".", 1)[-1].lower()
    return (
        tld.startswith("xn--")
        or tld in _KNOWN_TLDS
        or registrable_domain(host.lower()) in SHORTENER_DOMAINS
    )


def extract_urls(text: str) -> list[str]:
    """Return refanged URL strings found in ``text`` (order preserved, de-duplicated)."""
    found: list[str] = []
    clean = refang(text)
    for m in _URL_RE.finditer(clean):
        host = m.group("host")
        rest = m.group("rest") or ""
        if m.group("scheme") is None and m.start() > 0 and clean[m.start() - 1] == "@":
            continue  # e-mail domain or tail of a longer token
        if not _accept_candidate(m.group("scheme") is not None, host):
            continue
        rest = rest.rstrip(_TRAILING_PUNCT)
        url = (m.group("scheme") or "") + host + rest
        if url not in found:
            found.append(url)
    return found


def _flags_for(url: str, host: str, ascii_host: str, official: frozenset[str]) -> frozenset[str]:
    flags: set[str] = set()
    parts = urlsplit(url if "://" in url else "//" + url)
    path = parts.path.lower()
    query = parse_qs(parts.query.lower())
    if path.endswith(".apk") or "apk" in query.get("download", []):
        flags.add(APK_DOWNLOAD)
    if _is_ip(host):
        flags.add(IP_LITERAL)
    else:
        if any(t in host for t in GOV_TOKENS) and not (host == "gov.vn" or host.endswith(".gov.vn")):
            flags.add(GOV_SPOOF)
        if any(t in host for t in BRAND_TOKENS) and not _is_official(host, official):
            flags.add(BRAND_LOOKALIKE)
        if host.rsplit(".", 1)[-1] in RISKY_TLDS:
            flags.add(RISKY_TLD)
        if registrable_domain(host) in SHORTENER_DOMAINS:
            flags.add(SHORTENER)
    if "xn--" in ascii_host or any(ord(c) > 127 for c in host):
        flags.add(PUNYCODE)
    return frozenset(flags)


def check_urls(text: str) -> list[UrlCheckResult]:
    """Extract and heuristically flag every URL in ``text`` (no network)."""
    official = _official_domains()
    results: list[UrlCheckResult] = []
    seen: set[tuple[str, frozenset[str]]] = set()
    for url in extract_urls(text):
        raw_host = urlsplit(url if "://" in url else "//" + url).hostname or ""
        host = normalize_host(raw_host)
        if not host:
            continue
        flags = _flags_for(url, host, _to_ascii_host(host), official)
        key = (url.lower(), flags)
        if key in seen:
            continue
        seen.add(key)
        results.append(UrlCheckResult(url, host, registrable_domain(host), flags))
    return results


class SafeBrowsingClient:
    """Google Safe Browsing v4 lookup. Disabled unless an API key is configured."""

    ENDPOINT = "https://safebrowsing.googleapis.com/v4/threatMatches:find"
    TIMEOUT_S = 0.8

    def __init__(self, api_key: str, client: httpx.AsyncClient | None = None) -> None:
        self._api_key = api_key.strip()
        self._client = client

    @property
    def enabled(self) -> bool:
        return bool(self._api_key)

    async def lookup(self, urls: list[str], trace: TraceRecorder | None = None) -> set[str]:
        """Return the subset of ``urls`` reported as threats. Errors yield an empty set."""
        if not self.enabled or not urls:
            return set()
        body = {
            "client": {"clientId": "momo-guardian", "clientVersion": "0.1.0"},
            "threatInfo": {
                "threatTypes": [
                    "MALWARE",
                    "SOCIAL_ENGINEERING",
                    "UNWANTED_SOFTWARE",
                    "POTENTIALLY_HARMFUL_APPLICATION",
                ],
                "platformTypes": ["ANY_PLATFORM"],
                "threatEntryTypes": ["URL"],
                "threatEntries": [{"url": u} for u in urls],
            },
        }
        started = trace.elapsed_ms() if trace else 0
        try:
            if self._client is not None:
                resp = await self._client.post(
                    self.ENDPOINT, params={"key": self._api_key}, json=body, timeout=self.TIMEOUT_S
                )
            else:
                async with httpx.AsyncClient(timeout=self.TIMEOUT_S) as client:
                    resp = await client.post(self.ENDPOINT, params={"key": self._api_key}, json=body)
            resp.raise_for_status()
            matches = resp.json().get("matches", [])
            hits = {m["threat"]["url"] for m in matches if m.get("threat", {}).get("url") in urls}
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            if trace:
                trace.record(
                    "tool",
                    "safe_browsing",
                    "error",
                    {"error": type(exc).__name__},
                    t_start_ms=started,
                    duration_ms=trace.elapsed_ms() - started,
                )
            return set()
        if trace:
            trace.record(
                "tool",
                "safe_browsing",
                "ok",
                {"hits": len(hits)},
                t_start_ms=started,
                duration_ms=trace.elapsed_ms() - started,
            )
        return hits


async def check_urls_with_safe_browsing(
    text: str, client: SafeBrowsingClient, trace: TraceRecorder | None = None
) -> list[UrlCheckResult]:
    """Heuristic check merged with Safe Browsing hits (``SAFE_BROWSING_HIT`` flag)."""
    results = check_urls(text)
    if not client.enabled:
        return results
    hits = await client.lookup([r.url for r in results], trace)
    return [
        UrlCheckResult(r.url, r.domain, r.registrable_domain, r.flags | {SAFE_BROWSING_HIT})
        if r.url in hits
        else r
        for r in results
    ]
