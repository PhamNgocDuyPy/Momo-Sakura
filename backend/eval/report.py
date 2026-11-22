"""pass^k computation and ``eval_report.md`` rendering for the Eval_Harness."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

GROUP_ORDER = ("red-risk", "injection", "PII", "cold-start", "assistant")

EVIDENCE_BOUNDARY = (
    "pass^k với MockLLM chỉ chứng minh Control Plane chạy đúng; "
    "độ ổn định của LLM thật phải đo lại với provider thật"
)

FLOW_A_P95_TARGET_MS = 200
STAGE2_P95_TARGET_MS = 250


@dataclass
class ScenarioStats:
    scenario_id: str
    group: str
    runs: int
    passes: int
    # Mismatches of the first failing run, as ``"<endpoint>: <mismatch>"``.
    failures: list[str] = field(default_factory=list)


def pass_hat_k(passes: int, runs: int, k: int) -> float:
    """tau-bench per-scenario estimator ``C(c, k) / C(n, k)`` (0 when ``c < k``)."""
    if k < 1 or runs < k:
        raise ValueError(f"need 1 <= k <= runs (k={k}, runs={runs})")
    if not 0 <= passes <= runs:
        raise ValueError(f"passes must be within 0..runs (passes={passes}, runs={runs})")
    return math.comb(passes, k) / math.comb(runs, k)


def pass_at_k(stats: Sequence[ScenarioStats], k: int) -> float | None:
    """Mean of per-scenario ``C(c_i, k) / C(n, k)``; ``None`` for an empty sequence."""
    if not stats:
        return None
    return sum(pass_hat_k(s.passes, s.runs, k) for s in stats) / len(stats)


def p95(values: Sequence[float]) -> float | None:
    """Nearest-rank 95th percentile; ``None`` for no samples."""
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(0.95 * len(ordered)) - 1)]


def group_scores(stats: Sequence[ScenarioStats], k: int) -> dict[str, float | None]:
    groups = list(GROUP_ORDER) + sorted({s.group for s in stats} - set(GROUP_ORDER))
    return {g: pass_at_k([s for s in stats if s.group == g], k) for g in groups}


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100:.1f}%"


def _ms(value: float | None, target: int) -> str:
    if value is None:
        return "n/a"
    return f"{value:.0f} ms ({'đạt' if value < target else 'KHÔNG đạt'} mục tiêu < {target} ms)"


def render_report(
    stats: Sequence[ScenarioStats],
    *,
    runs: int,
    k: int,
    provider: str,
    flow_a_latencies_ms: Sequence[float],
    flow_b_stage2_ms: Sequence[float],
    generated_at: datetime | None = None,
) -> str:
    when = (generated_at or datetime.now(timezone.utc)).isoformat(timespec="seconds")
    lines = [
        "# Eval report",
        "",
        f"- LLM provider: `{provider}`",
        f"- Thời điểm: {when}",
        f"- Số lần chạy mỗi kịch bản (n): {runs}",
        f"- k: {k}",
        f"- Số kịch bản: {len(stats)}",
        "",
        f"> {EVIDENCE_BOUNDARY}.",
        "",
        f"## pass^{k}",
        "",
        f"Tổng: **{_pct(pass_at_k(stats, k))}**",
        "",
        "| Nhóm | Số kịch bản | " + f"pass^{k} |",
        "|---|---|---|",
    ]
    for group, score in group_scores(stats, k).items():
        count = sum(1 for s in stats if s.group == group)
        lines.append(f"| {group} | {count} | {_pct(score)} |")
    lines += [
        "",
        "## Độ trễ",
        "",
        f"- Flow A `latency_ms` p95 ({len(flow_a_latencies_ms)} mẫu): {_ms(p95(flow_a_latencies_ms), FLOW_A_P95_TARGET_MS)}",
        f"- Flow B `stage2` p95 ({len(flow_b_stage2_ms)} mẫu): {_ms(p95(flow_b_stage2_ms), STAGE2_P95_TARGET_MS)}",
        "",
        "Độ trễ đo trên máy local với Sandbox_Provider, không đại diện cho production.",
        "",
        "## Kịch bản không đạt",
        "",
    ]
    failing = [s for s in stats if s.passes < s.runs]
    if not failing:
        lines.append(f"Không có. Mọi kịch bản đạt {runs}/{runs} lần.")
    for s in failing:
        lines.append(f"### {s.scenario_id} ({s.group}): đạt {s.passes}/{s.runs}")
        lines += [f"- {m}" for m in s.failures] or ["- (không có chi tiết)"]
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_report(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8", newline="\n")
