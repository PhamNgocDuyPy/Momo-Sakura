"""Hypothesis strategies for deterministic signals, floors and floor sets."""

from __future__ import annotations

from dataclasses import dataclass

from hypothesis import strategies as st

from guardian.policy.floors import Floor, FloorSet
from guardian.reason_codes import REGISTRY
from guardian.schemas.api_models import Signals
from guardian.schemas.enums import Cue, DecisionTier, HardSource, QrResult, ScamPlaybook

BOUNDARY_GNN = (0.0, 0.6, 0.84, 0.85, 0.86, 1.0)
BOUNDARY_AMOUNTS = (
    8_999_999, 9_000_000, 9_000_001, 9_999_999, 10_000_000, 10_000_001,
    19_999_999, 20_000_000, 20_000_001,
)  # fmt: skip

_CODES = sorted(REGISTRY)
_RULES = ["R1", "R2", "R3", "R4", "R5", "R6", "TIER1", "URL", "MEMORY", "PLAYBOOK", "CUE"]


@dataclass(frozen=True)
class SignalSet:
    """Deterministic engine inputs (raw tool outputs). Not the API envelope: see ``api_signals``."""
    simo_hit: bool
    gnn_mule_score: float
    fan_in_per_hour: int
    account_age_days: int
    amount_vnd: int
    total_24h_vnd: int
    qr_result: QrResult | None
    prefilter_score: float
    contains_prompt_injection: bool


gnn_scores = st.one_of(st.sampled_from(BOUNDARY_GNN), st.floats(0.0, 1.0, allow_nan=False))
amounts = st.one_of(st.sampled_from(BOUNDARY_AMOUNTS), st.integers(1_000, 50_000_000))
totals_24h = st.one_of(
    st.sampled_from((0, 10_999_999, 11_000_000, 19_999_999, 20_000_000)),
    st.integers(0, 60_000_000),
)


@st.composite
def signals(draw: st.DrawFn) -> SignalSet:
    return SignalSet(
        simo_hit=draw(st.booleans()),
        gnn_mule_score=draw(gnn_scores),
        fan_in_per_hour=draw(st.integers(0, 40)),
        account_age_days=draw(st.integers(0, 3650)),
        amount_vnd=draw(amounts),
        total_24h_vnd=draw(totals_24h),
        qr_result=draw(st.none() | st.sampled_from(list(QrResult))),
        prefilter_score=draw(st.floats(0.0, 1.0, allow_nan=False)),
        contains_prompt_injection=draw(st.booleans()),
    )


@st.composite
def floors(draw: st.DrawFn) -> Floor:
    code = draw(st.sampled_from(_CODES))
    spec = REGISTRY[code]
    tier = draw(st.sampled_from([t for t in DecisionTier if t >= spec.min_tier]))
    hard_source = None
    if tier == DecisionTier.HARD_HOLD:
        hard_source = draw(st.sampled_from(sorted(spec.hard_sources or set(HardSource))))
    removable = draw(st.sampled_from([frozenset(), frozenset({"FAST_UNBLOCK"}), frozenset({"CONTEXT_IN_STORE"})]))
    return Floor(tier, code, draw(st.sampled_from(_RULES)), hard_source, removable)  # type: ignore[arg-type]


@st.composite
def floorsets(draw: st.DrawFn, max_size: int = 8) -> FloorSet:
    return FloorSet(draw(st.lists(floors(), max_size=max_size)))


@st.composite
def api_signals(draw: st.DrawFn) -> Signals:
    """The enum-and-number `Signals` block of `CheckResponse`."""
    return Signals(
        scam_playbook=draw(st.none() | st.sampled_from(list(ScamPlaybook))),
        manipulation_cues=draw(st.lists(st.sampled_from(list(Cue)), unique=True, max_size=6)),
        url_flags=draw(st.lists(st.sampled_from(['RISKY_TLD', 'APK_DOWNLOAD', 'GOV_SPOOF']), unique=True, max_size=3)),
        prefilter_score=draw(st.none() | st.floats(0.0, 1.0, allow_nan=False)),
    )
