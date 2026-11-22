"""Minimal dependency container. Later tasks register stores, llm, policy."""
from __future__ import annotations

from dataclasses import dataclass, field

from guardian.config import Settings
from guardian.providers.base import RiskDataProvider, WalletDataProvider
from guardian.providers.clock import Clock, SandboxClock, SystemClock
from guardian.providers.fixture_loader import resolve_fixtures_dir
from guardian.providers.sandbox_risk import SandboxRiskProvider
from guardian.providers.sandbox_wallet import SandboxWalletProvider
from guardian.control_plane.assistant import AssistantService
from guardian.control_plane.flow_a import FlowAGate
from guardian.control_plane.flow_b import FlowBOrchestrator
from guardian.control_plane.pending_confirm import PendingConfirmStore
from guardian.providers.sandbox_reference import SandboxReferenceProvider
from guardian.llm.base import LLMClient
from guardian.llm.factory import build_llm
from guardian.policy.engine import PolicyEngine
from guardian.control_plane.verdict_store import VerdictStore
from guardian.stores.audit import AuditLog
from guardian.stores.ledger import Ledger
from guardian.stores.risk_memory import RiskMemory
from guardian.stores.shield_stats import ShieldStats


@dataclass
class Container:
    settings: Settings
    risk_provider: RiskDataProvider
    wallet_provider: WalletDataProvider
    sandbox_clock: Clock
    system_clock: Clock
    shield_stats: ShieldStats = field(default_factory=ShieldStats)
    risk_memory: RiskMemory = field(default_factory=RiskMemory)
    audit: AuditLog = field(default_factory=lambda: AuditLog("./var/audit.jsonl"))
    ledger: Ledger = field(default_factory=Ledger)
    verdict_store: VerdictStore = field(default_factory=VerdictStore)
    pending_confirm: PendingConfirmStore = field(default_factory=PendingConfirmStore)
    policy: PolicyEngine = field(default_factory=PolicyEngine)
    flow_a: FlowAGate = field(init=False)
    flow_b: FlowBOrchestrator = field(init=False)
    assistant: AssistantService = field(init=False)
    # Never passed to FlowAGate (Flow A must not call an LLM, Req 6.2).
    llm: LLMClient = field(init=False)


def build_container(settings: Settings) -> Container:
    # Raises FixtureError (naming the file) when a fixture is missing or corrupt.
    fixtures_dir = resolve_fixtures_dir(settings.fixtures_dir)
    system_clock = SystemClock()
    wallet_provider = SandboxWalletProvider(fixtures_dir)
    container = Container(
        settings=settings,
        risk_memory=RiskMemory(settings.risk_memory_ttl_hours, system_clock),
        audit=AuditLog(settings.audit_log_path),
        ledger=Ledger(system_clock),
        verdict_store=VerdictStore(system_clock),
        pending_confirm=PendingConfirmStore(system_clock),
        risk_provider=SandboxRiskProvider(fixtures_dir),
        wallet_provider=wallet_provider,
        sandbox_clock=SandboxClock(settings.sandbox_now),
        system_clock=system_clock,
        policy=PolicyEngine(
            settings.fan_in_velocity_threshold,
            wallet=wallet_provider,
            prefilter_soft_threshold=settings.prefilter_soft_threshold,
        ),
    )
    container.llm = build_llm(settings)
    container.flow_a = FlowAGate(
        risk_provider=container.risk_provider,
        wallet_provider=container.wallet_provider,
        risk_memory=container.risk_memory,
        ledger=container.ledger,
        verdict_store=container.verdict_store,
        pending_confirm=container.pending_confirm,
        audit=container.audit,
        shield_stats=container.shield_stats,
        policy=container.policy,
        session_secret=settings.session_hash_secret,
        hotline=settings.momo_hotline,
        clock=system_clock,
    )
    container.flow_b = FlowBOrchestrator(
        risk_provider=container.risk_provider,
        wallet_provider=container.wallet_provider,
        reference_provider=SandboxReferenceProvider(fixtures_dir),
        risk_memory=container.risk_memory,
        verdict_store=container.verdict_store,
        pending_confirm=container.pending_confirm,
        audit=container.audit,
        shield_stats=container.shield_stats,
        policy=container.policy,
        llm=container.llm,
        session_secret=settings.session_hash_secret,
        ledger=container.ledger,
        hotline=settings.momo_hotline,
        clock=system_clock,
        sandbox_clock=container.sandbox_clock,
        llm_timeout_ms=settings.llm_timeout_ms,
        debug_enabled=settings.guardian_debug,
    )
    container.assistant = AssistantService(
        llm=container.llm,
        wallet_provider=container.wallet_provider,
        policy=container.policy,
        sandbox_clock=container.sandbox_clock,
        session_secret=settings.session_hash_secret,
        llm_timeout_ms=settings.llm_timeout_ms,
    )
    return container
