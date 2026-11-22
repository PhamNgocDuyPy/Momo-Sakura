import pytest

from guardian.control_plane.session import RequestContext
from guardian.control_plane.tool_runner import (
    ALLOWED_TOOLS,
    Abort,
    Allow,
    ToolNotAllowed,
    ToolRunner,
)
from guardian.schemas.enums import StopCode

SID = "123e4567-e89b-42d3-a456-426614174000"


def _ctx() -> RequestContext:
    return RequestContext.create(SID, "FLOW_B", "secret")


class _Policy:
    def __init__(self, decision=None):
        self.decision = decision or Allow()
        self.after: list[str] = []

    def before_call(self, name, args, ctx):
        return self.decision

    def after_call(self, name, result, ctx):
        self.after.append(name)


async def test_denied_tool_raises_and_traces():
    ctx = _ctx()
    runner = ToolRunner({})
    with pytest.raises(ToolNotAllowed):
        await runner.call("transfer_money", ctx)
    assert ctx.trace.steps[-1].status == "denied"


async def test_ok_call_runs_hooks_and_traces():
    ctx = _ctx()
    policy = _Policy()

    async def check_urls(ctx, urls):
        return len(urls)

    out = await ToolRunner({"check_urls": check_urls}, policy).call("check_urls", ctx, urls=["a"])
    assert out.result == 1 and not out.aborted
    assert policy.after == ["check_urls"]
    assert ctx.trace.steps[0].status == "ok"


async def test_abort_skips_tool():
    ctx = _ctx()
    called = []
    policy = _Policy(Abort(StopCode.ABORT_WAIT_NAPAS_NAME_USER_CONFIRM, "UNCONFIRMED_ACCOUNT_ABORTED"))
    runner = ToolRunner({"lookup_recipient_risk_and_simo": lambda ctx: called.append(1)}, policy)
    out = await runner.call("lookup_recipient_risk_and_simo", ctx)
    assert out.aborted and not called and not policy.after
    assert ctx.stop_codes == [StopCode.ABORT_WAIT_NAPAS_NAME_USER_CONFIRM]
    assert ctx.trace.steps[0].status == "aborted"


def test_registry_must_be_subset_of_allowlist():
    with pytest.raises(ValueError):
        ToolRunner({"evil": lambda ctx: None})
    assert "quarantined_extract" in ALLOWED_TOOLS
