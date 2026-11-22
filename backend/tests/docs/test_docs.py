"""Structure checks for docs/FLOWS_AND_GLOSSARY.md."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

DOC = Path(__file__).resolve().parents[3] / "docs" / "FLOWS_AND_GLOSSARY.md"
TEXT = DOC.read_text(encoding="utf-8")


def _section(title_regex: str) -> str:
    """Return the text from the first heading matching ``title_regex`` to the next heading of any level."""
    m = re.search(rf"^#{{2,4}} (?:\d+\. )?(?:{title_regex}).*$", TEXT, re.MULTILINE)
    assert m, f"heading matching {title_regex!r} not found"
    rest = TEXT[m.end():]
    nxt = re.search(r"^#{2,4} ", rest, re.MULTILINE)
    return rest[: nxt.start()] if nxt else rest


def test_mermaid_blocks_exist() -> None:
    assert "```mermaid" in TEXT


@pytest.mark.parametrize(
    "title",
    ["Flow A", "Flow B", "Risk_Memory", "F1", "F2", "F3", "F4", "F5", "F6", "F7"],
)
def test_mermaid_diagram_under_heading(title: str) -> None:
    body = _section(re.escape(title) + r"(?:\s|$)")
    assert "```mermaid" in body, f"no mermaid diagram under heading for {title}"


def test_flow_b_mentions_progressive_disclosure_and_circuit_breaker() -> None:
    body = _section("Flow B")
    assert "circuit breaker" in body.lower()
    assert "progressive disclosure" in body.lower()


def test_real_sandbox_table() -> None:
    body = _section(".*Thật / Sandbox")
    assert re.search(r"^\|\s*Thành phần\s*\|\s*Trạng thái\s*\|", body, re.MULTILINE)
    assert "| Sandbox |" in body and "| Thật" in body


def test_glossary_table() -> None:
    body = _section("Bảng thuật ngữ")
    assert re.search(r"^\|\s*Thuật ngữ\s*\|", body, re.MULTILINE)
    for term in [
        "APP fraud", "VietQR", "EMVCo", "TLV", "CRC-16", "BIN", "NAPAS 247", "SIMO",
        "GNN mule", "fan-in", "SOFT_FRICTION", "Reason code", "Stop code", "cold-start",
        "honesty invariant", "Context Elicitation", "Calm Shield", "Fast Unblock",
        "Thông tư 50", "Luật 91/2025", "CaMeL", "P-LLM", "taint", "AgentSpec",
        "temporal stealth", "circuit breaker", "progressive disclosure", "pass^k",
        "agent harness", "eval harness", "sandbox provider",
    ]:
        assert term in body, f"glossary term missing: {term}"


def test_stop_codes_listed() -> None:
    from guardian.schemas.enums import StopCode

    for code in StopCode:
        assert code.value in TEXT


def test_mobile_roadmap_section() -> None:
    body = _section("Lộ trình mobile")
    for keyword in [
        "share sheet", "NotificationListener", "SYSTEM_ALERT_WINDOW",
        "iOS Share Extension", "Accessibility Service",
    ]:
        assert keyword in body, f"mobile roadmap missing: {keyword}"


def test_evidence_boundary_note() -> None:
    assert "MockLLM" in TEXT and "Control Plane" in TEXT

def test_user_io_section_has_three_subtables() -> None:
    m = re.search(r"^## Người dùng đưa vào gì, nhận lại gì\s*$", TEXT, re.MULTILINE)
    assert m, "section 'Người dùng đưa vào gì, nhận lại gì' not found"
    assert m.start() < TEXT.index("## 2. "), "section must sit near the top, before section 2"
    rest = TEXT[m.end():]
    nxt = re.search(r"^## ", rest, re.MULTILINE)
    body = rest[: nxt.start()] if nxt else rest
    assert re.search(r"^### Điểm vào\s*$", body, re.MULTILINE)
    assert re.search(r"^### Kết quả người dùng thấy\s*$", body, re.MULTILINE)
    assert re.search(r"^### Ví dụ đầu–cuối\s*$", body, re.MULTILINE)
    entry = body.split("### Điểm vào", 1)[1].split("### Kết quả người dùng thấy", 1)[0]
    assert re.search(r"^\| Điểm vào \| Người dùng làm gì \(đầu vào\) \| Guardian đọc gì \| Dữ liệu rời khỏi thiết bị \|", entry, re.MULTILINE)
    for keyword in ["Dán & kiểm tra", "Alt+G", "Tự động bảo vệ", "Guardian đã đọc N tin nhắn", "15 tin nhắn"]:
        assert keyword in entry, f"entry-point table missing: {keyword}"
    results = body.split("### Kết quả người dùng thấy", 1)[1].split("### Đầu vào và đầu ra", 1)[0]
    assert re.search(r"^\| \| ALLOW \| SOFT_FRICTION \| HARD_HOLD \|", results, re.MULTILINE)
    for keyword in ["Chưa thấy dấu hiệu bất thường", "Đang phân tích tiếp", "Chuyển ngay", "Mở chặn nhanh"]:
        assert keyword in results, f"result table missing: {keyword}"
    assert "RC_ACCOUNT_SWAP_REQUEST" in body.split("### Ví dụ đầu–cuối", 1)[1]
