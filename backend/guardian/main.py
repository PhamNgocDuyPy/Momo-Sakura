"""FastAPI application factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from guardian.api import (
    assistant,
    debug,
    eval as eval_api,
    flow_a,
    flow_b,
    health,
    name,
    precheck,
    qr,
    spend,
    split,
    transfer,
    wallet,
)
from guardian.api.deps import GuardianError
from guardian.config import VERSION, Settings, get_settings, validate_startup
from guardian.container import build_container


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        validate_startup(settings)
        app.state.container = build_container(settings)
        yield

    app = FastAPI(title="MoMo Guardian", version=VERSION, lifespan=lifespan)
    # Also available without running lifespan (e.g. httpx.ASGITransport in tests).
    app.state.container = build_container(settings)

    origins = settings.cors_origin_list()
    if origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    @app.exception_handler(GuardianError)
    async def _guardian_error(_: Request, exc: GuardianError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.error,
                "message_vi": exc.message_vi,
                "details": exc.details,
            },
        )

    app.include_router(health.router)
    app.include_router(wallet.router)
    app.include_router(qr.router)
    app.include_router(flow_a.router)
    app.include_router(transfer.router)
    app.include_router(precheck.router)
    app.include_router(flow_b.router)
    app.include_router(name.router)
    app.include_router(assistant.router)
    app.include_router(spend.router)
    app.include_router(split.router)
    app.include_router(debug.router)
    app.include_router(eval_api.router)
    return app


def _default_app() -> FastAPI:
    return create_app()


app = _default_app()
