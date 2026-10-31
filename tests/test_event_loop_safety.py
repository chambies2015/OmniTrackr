"""Database work must never run on the event loop, and requests must never exhaust the pool.

An async route that queries the database runs those queries on the server's only
event loop. When every pooled connection was busy, the loop itself waited for one and
the whole site froze (one dashboard opening was enough to trigger it).
"""
import ast
import asyncio
import inspect
import pathlib
import threading
import time

from app import dependencies, release_radar, title_charts

APP = pathlib.Path(__file__).resolve().parents[1] / "app"
ROUTE_METHODS = {"get", "post", "put", "patch", "delete", "head", "api_route"}


def _async_db_routes_without_awaits():
    found = []
    for path in [*sorted((APP / "routers").glob("*.py")), APP / "main.py"]:
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.AsyncFunctionDef) or "get_db" not in ast.unparse(node.args):
                continue
            if not any(isinstance(d, ast.Call) and getattr(d.func, "attr", "") in ROUTE_METHODS for d in node.decorator_list):
                continue
            if not any(isinstance(x, (ast.Await, ast.AsyncWith, ast.AsyncFor)) for x in ast.walk(node)):
                found.append(f"{path.name}:{node.lineno} {node.name}")
    return found


def test_routes_that_only_use_the_database_are_plain_functions():
    assert _async_db_routes_without_awaits() == []


def test_member_lookup_runs_in_the_threadpool():
    assert not inspect.iscoroutinefunction(dependencies.get_current_user)
    assert not inspect.iscoroutinefunction(dependencies.get_optional_current_user)


def test_sessions_wait_for_a_slot_instead_of_draining_the_pool(monkeypatch):
    opened, peak, closed = [], [0], []

    class FakeSession:
        def close(self):
            closed.append(self)

    def factory():
        session = FakeSession()
        opened.append(session)
        return session

    monkeypatch.setattr(dependencies, "SessionLocal", factory)
    monkeypatch.setattr(dependencies, "SESSION_SLOTS", 2)
    monkeypatch.setattr(dependencies, "_gates", {})

    async def request():
        generator = dependencies.get_db()
        await generator.__anext__()
        peak[0] = max(peak[0], len(opened) - len(closed))
        await asyncio.sleep(0.01)
        await generator.aclose()

    async def run():
        await asyncio.gather(*(request() for _ in range(8)))

    asyncio.run(run())
    assert len(opened) == len(closed) == 8
    assert peak[0] == 2


def test_radar_warm_from_a_worker_thread_hands_the_fetch_to_the_loop(monkeypatch):
    cache = release_radar.RadarCache(None)
    started = []
    monkeypatch.setattr(cache, "_start_refresh", lambda client, window: started.append(window))
    window = release_radar.featured_window("movies")

    release_radar.bind_event_loop(None)
    worker = threading.Thread(target=cache.warm, args=(object(), window))
    worker.start()
    worker.join()
    assert started == []  # No loop to hand it to: skipped, never an error.

    async def run():
        release_radar.bind_event_loop(asyncio.get_running_loop())
        try:
            await asyncio.to_thread(cache.warm, object(), window)
            await asyncio.sleep(0)
        finally:
            release_radar.bind_event_loop(None)

    asyncio.run(run())
    assert started == [window]


def test_an_expired_chart_is_rebuilt_by_one_request_at_a_time(monkeypatch):
    calls = []

    def slow_build(db, kind):
        calls.append(kind)
        time.sleep(0.2)
        return {"kind": kind, "ranked": [], "build": len(calls)}

    monkeypatch.setattr(title_charts, "build", slow_build)
    title_charts.clear_cache()
    first = title_charts.chart(None, "movie")
    assert first["build"] == 1

    # Expire it, then ask from several threads at once: one rebuilds, the rest keep the old chart.
    with title_charts._lock:
        title_charts._cache["movie"] = (time.monotonic() - title_charts.CACHE_SECONDS - 1, first)
    results = []
    threads = [threading.Thread(target=lambda: results.append(title_charts.chart(None, "movie"))) for _ in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len(calls) == 2
    assert sorted(result["build"] for result in results).count(2) >= 1
    assert title_charts.chart(None, "movie")["build"] == 2
