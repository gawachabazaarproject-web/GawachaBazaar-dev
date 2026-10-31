"""Catalog read-through cache: hit/miss, instant invalidation on committed
catalog writes, and fail-safe behaviour. Database-free (in-memory SQLite and a
fake Redis), so it runs without the disposable Postgres test database."""

import time

import pytest
from pydantic import BaseModel
from sqlalchemy import Column, Integer, create_engine
from sqlalchemy.orm import Session, declarative_base

from app.core.config import settings
from app.services import catalog_cache as cc
from app.services.catalog_cache import CatalogCache
from app.services.routing.cache import RouteCache


class Item(BaseModel):
    id: int
    name: str


class FakeRedis:
    def __init__(self) -> None:
        self.data: dict[str, bytes] = {}
        self.down = False

    def _check(self) -> None:
        if self.down:
            raise ConnectionError("redis down")

    def get(self, key):
        self._check()
        return self.data.get(key)

    def set(self, key, value, ex=None, nx=False):
        self._check()
        self.data[key] = value.encode() if isinstance(value, str) else value
        return True

    def incr(self, key):
        self._check()
        self.data[key] = str(int(self.data.get(key, b"0")) + 1).encode()
        return int(self.data[key])


@pytest.fixture
def ttl(monkeypatch):
    monkeypatch.setattr(settings, "CATALOG_CACHE_TTL_SECONDS", 60)


def _loader(counter: list[int]):
    def load() -> Item:
        counter[0] += 1
        return Item(id=1, name=f"v{counter[0]}")

    return load


def test_second_call_is_served_from_cache(ttl):
    cache, calls = CatalogCache(RouteCache()), [0]
    first = cache.get_or_load("p", {"id": 1}, Item, _loader(calls))
    second = cache.get_or_load("p", {"id": 1}, Item, _loader(calls))
    assert first == second == Item(id=1, name="v1")
    assert calls[0] == 1


def test_params_are_part_of_the_key(ttl):
    cache, calls = CatalogCache(RouteCache()), [0]
    cache.get_or_load("p", {"id": 1}, Item, _loader(calls))
    cache.get_or_load("p", {"id": 2}, Item, _loader(calls))
    assert calls[0] == 2


def test_bump_invalidates_immediately(ttl):
    cache, calls = CatalogCache(RouteCache()), [0]
    cache.get_or_load("p", {}, Item, _loader(calls))
    cache.bump()
    assert cache.get_or_load("p", {}, Item, _loader(calls)).name == "v2"


def test_list_response_types_round_trip(ttl):
    cache = CatalogCache(RouteCache())
    load = lambda: [Item(id=1, name="a"), Item(id=2, name="b")]  # noqa: E731
    assert cache.get_or_load("l", {}, list[Item], load) == load()
    assert cache.get_or_load("l", {}, list[Item], lambda: pytest.fail("not cached")) == load()


def test_zero_ttl_disables_caching(monkeypatch):
    monkeypatch.setattr(settings, "CATALOG_CACHE_TTL_SECONDS", 0)
    cache, calls = CatalogCache(RouteCache()), [0]
    cache.get_or_load("p", {}, Item, _loader(calls))
    cache.get_or_load("p", {}, Item, _loader(calls))
    assert calls[0] == 2


def test_loader_errors_are_not_cached(ttl):
    cache = CatalogCache(RouteCache())

    def boom():
        raise LookupError("missing")

    with pytest.raises(LookupError):
        cache.get_or_load("p", {}, Item, boom)
    assert cache.get_or_load("p", {}, Item, lambda: Item(id=9, name="ok")).id == 9


def test_shared_redis_version_is_seen_by_other_workers(ttl, monkeypatch):
    monkeypatch.setattr(settings, "REDIS_URL", "redis://fake")
    redis = FakeRedis()
    a, b = CatalogCache(RouteCache(redis)), CatalogCache(RouteCache(redis))
    calls = [0]
    a.get_or_load("p", {}, Item, _loader(calls))
    assert b.get_or_load("p", {}, Item, _loader(calls)).name == "v1"  # shared hit
    a.bump()
    assert b.get_or_load("p", {}, Item, _loader(calls)).name == "v2"  # b sees a's bump


def test_redis_outage_falls_back_to_loader_and_never_serves_stale(ttl, monkeypatch):
    monkeypatch.setattr(settings, "REDIS_URL", "redis://fake")
    redis = FakeRedis()
    cache, calls = CatalogCache(RouteCache(redis)), [0]
    cache.get_or_load("p", {}, Item, _loader(calls))  # cached under version r0
    redis.down = True
    cache.bump()  # the invalidation could not reach Redis
    redis.down = False
    store = cache._store
    store._down_until = 0.0  # breaker window elapsed
    # Entry cached before the failed bump must not come back.
    assert cache.get_or_load("p", {}, Item, _loader(calls)).name == "v2"
    assert time.monotonic() < cache._bypass_until


def test_redis_outage_on_read_goes_straight_to_the_database(ttl, monkeypatch):
    monkeypatch.setattr(settings, "REDIS_URL", "redis://fake")
    redis = FakeRedis()
    redis.down = True
    cache, calls = CatalogCache(RouteCache(redis)), [0]
    assert cache.get_or_load("p", {}, Item, _loader(calls)).name == "v1"
    assert cache.get_or_load("p", {}, Item, _loader(calls)).name == "v2"


# --- automatic invalidation from committed writes ---------------------------

Base = declarative_base()


class Ad(Base):  # table name is on the watched list
    __tablename__ = "ads"
    id = Column(Integer, primary_key=True)
    n = Column(Integer, default=0)


class Unrelated(Base):
    __tablename__ = "unrelated_things"
    id = Column(Integer, primary_key=True)


@pytest.fixture
def session(monkeypatch):
    fresh = CatalogCache(RouteCache())
    monkeypatch.setattr(cc, "catalog_cache", fresh)
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s, fresh


def test_committed_watched_insert_bumps_version(session):
    s, cache = session
    before = cache._local_version
    s.add(Ad())
    s.commit()
    assert cache._local_version == before + 1


def test_unrelated_table_does_not_bump(session):
    s, cache = session
    before = cache._local_version
    s.add(Unrelated())
    s.commit()
    assert cache._local_version == before


def test_rollback_does_not_bump(session):
    s, cache = session
    before = cache._local_version
    s.add(Ad())
    s.flush()
    s.rollback()
    s.commit()
    assert cache._local_version == before


def test_bulk_update_and_delete_bump(session):
    s, cache = session
    s.add(Ad())
    s.commit()
    before = cache._local_version
    s.query(Ad).update({"n": 5})
    s.commit()
    assert cache._local_version == before + 1
    s.query(Ad).delete()
    s.commit()
    assert cache._local_version == before + 2
