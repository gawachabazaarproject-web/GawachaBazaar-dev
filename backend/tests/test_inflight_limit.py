"""Load shedding: in-flight cap, queueing, 503 on queue timeout, probe bypass."""

import asyncio

import httpx
import pytest
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

from app.core.concurrency import InflightLimitMiddleware
from app.core.config import settings


def _app(max_inflight: int, queue_timeout: float):
    state = {"now": 0, "peak": 0}

    async def slow(_request):
        state["now"] += 1
        state["peak"] = max(state["peak"], state["now"])
        await asyncio.sleep(0.2)
        state["now"] -= 1
        return JSONResponse({"ok": True})

    async def health(_request):
        return JSONResponse({"status": "ok"})

    app = Starlette(routes=[Route("/slow", slow), Route("/health", health)])
    return InflightLimitMiddleware(app, max_inflight, queue_timeout), state


async def _client(app):
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t")


@pytest.mark.asyncio
async def test_concurrency_is_capped_and_excess_requests_queue() -> None:
    app, state = _app(max_inflight=3, queue_timeout=5)
    async with await _client(app) as c:
        responses = await asyncio.gather(*[c.get("/slow") for _ in range(9)])
    assert [r.status_code for r in responses] == [200] * 9
    assert state["peak"] == 3


@pytest.mark.asyncio
async def test_requests_waiting_too_long_are_shed_with_503() -> None:
    app, _ = _app(max_inflight=1, queue_timeout=0.05)
    async with await _client(app) as c:
        responses = await asyncio.gather(*[c.get("/slow") for _ in range(3)])
    codes = sorted(r.status_code for r in responses)
    assert codes == [200, 503, 503]
    shed = next(r for r in responses if r.status_code == 503)
    assert shed.headers["retry-after"] == "2" and shed.json()["code"] == "SERVER_BUSY"


@pytest.mark.asyncio
async def test_health_probe_bypasses_the_limit() -> None:
    app, _ = _app(max_inflight=1, queue_timeout=0.05)
    async with await _client(app) as c:
        slow = asyncio.create_task(c.get("/slow"))
        await asyncio.sleep(0.02)
        assert (await c.get("/health")).status_code == 200
        await slow


def test_default_inflight_cap_fits_inside_the_db_pool() -> None:
    assert 0 < settings.MAX_INFLIGHT_REQUESTS <= settings.DB_POOL_SIZE + settings.DB_MAX_OVERFLOW
