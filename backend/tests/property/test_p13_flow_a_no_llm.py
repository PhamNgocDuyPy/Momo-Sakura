# Feature: momo-guardian-web, Property 13: Flow A không gọi LLM
"""Property 13: Flow A không gọi LLM.

Any valid ``FlowAGate.check`` request makes zero LLMClient calls. A spy ``LLMClient`` that raises
when used is reachable from every place a LLM could be obtained (``guardian.llm`` package and its
factory); the gate itself takes no LLM dependency, and its module imports nothing from ``guardian.llm``.

**Validates: Requirements 6.2**
"""

from __future__ import annotations

import ast
import asyncio
import inspect
import json
import sys
import uuid
from pathlib import Path
from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st

import guardian.control_plane.flow_a as flow_a_module
from guardian.control_plane.flow_a import FlowAGate
from guardian.main import create_app
from guardian.schemas.api_models import DebugOverrides, FlowACheckRequest
from guardian.schemas.enums import SourceIntegrity
from guardian.tools.vietqr import encode_vietqr
from tests.conftest import make_settings
from tests.property.strategies.vietqr import vietqr_fields

_FIXTURES = Path(__file__).resolve().parents[3] / "fixtures"
_SANDBOX_ACCOUNTS = json.loads((_FIXTURES / "risk_sandbox.json").read_text(encoding="utf-8"))["accounts"]
_QR_SAMPLES = [v["payload"] for v in json.loads((_FIXTURES / "qr_samples.json").read_text(encoding="utf-8")).values()]


class LLMSpyError(AssertionError):
    pass


class SpyLLMClient:
    """Stands in for any LLMClient; every method raises and counts the call."""

    calls = 0

    def __getattr__(self, name: str) -> Any:
        def _boom(*_a: Any, **_k: Any) -> Any:
            type(self).calls += 1
            raise LLMSpyError(f"LLMClient.{name} called from Flow A")

        return _boom


@pytest.fixture(autouse=True)
def _llm_forbidden(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make any attempt to obtain an LLM during a Flow A call fail loudly."""
    SpyLLMClient.calls = 0
    # A lazy `import guardian.llm...` inside the gate raises ImportError -> request fails.
    for name in [n for n in sys.modules if n == "guardian.llm" or n.startswith("guardian.llm.")]:
        monkeypatch.delitem(sys.modules, name)
    monkeypatch.setitem(sys.modules, "guardian.llm", None)  # type: ignore[arg-type]


@st.composite
def check_requests(draw: st.DrawFn) -> FlowACheckRequest:
    kind = draw(st.sampled_from(["sandbox", "random", "qr_sample", "qr_encoded"]))
    amount = draw(
        st.one_of(
            st.sampled_from([9_000_000, 10_000_000, 20_000_000, 150_000]),
            st.integers(1_000, 100_000_000),
        )
    )
    integrity = draw(st.sampled_from(list(SourceIntegrity)))
    token = draw(st.one_of(st.none(), st.just(uuid.uuid4().hex)))
    qr: str | None = None
    if kind == "sandbox":
        acct = draw(st.sampled_from(_SANDBOX_ACCOUNTS))
        bank_bin, number = acct["bank_bin"], acct["account_number"]
    elif kind == "random":
        bank_bin = draw(st.from_regex(r"[0-9]{6}", fullmatch=True))
        number = draw(st.from_regex(r"[0-9]{6,19}", fullmatch=True))
    elif kind == "qr_sample":
        acct = draw(st.sampled_from(_SANDBOX_ACCOUNTS))
        bank_bin, number = acct["bank_bin"], acct["account_number"]
        qr = draw(st.sampled_from(_QR_SAMPLES))
    else:
        f = draw(vietqr_fields())
        bank_bin, number = f["bin"], f["account"]
        qr = encode_vietqr(**f)
    memo = draw(st.one_of(st.none(), st.text(max_size=60)))
    debug = None
    if qr is not None and draw(st.booleans()):
        debug = DebugOverrides(simulate_skip_qr_verify=True)
    return FlowACheckRequest(
        bank_bin=bank_bin,
        account_number=number,
        amount_vnd=amount,
        memo=memo,
        source_integrity=integrity,
        qr_payload=qr,
        confirmation_token=token,
        debug=debug,
    )


@pytest.fixture(scope="module")
def gate() -> FlowAGate:
    app = create_app(make_settings(guardian_debug=True, audit_log_path=str(_audit_path())))
    return app.state.container.flow_a  # type: ignore[no-any-return]


def _audit_path() -> Path:
    import tempfile

    return Path(tempfile.mkdtemp()) / "audit.jsonl"


@given(req=check_requests())
def test_flow_a_never_calls_llm(gate: FlowAGate, req: FlowACheckRequest) -> None:
    result = asyncio.run(gate.check(str(uuid.uuid4()), req))
    assert result.response.channel == "FLOW_A"
    assert SpyLLMClient.calls == 0


def test_gate_has_no_llm_dependency() -> None:
    params = inspect.signature(FlowAGate.__init__).parameters
    assert not any("llm" in p.lower() for p in params)


def test_flow_a_module_does_not_import_guardian_llm() -> None:
    tree = ast.parse(Path(flow_a_module.__file__).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert not any(a.name.startswith("guardian.llm") for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            assert not mod.startswith("guardian.llm")
            assert not (mod == "guardian" and any(a.name == "llm" for a in node.names))
