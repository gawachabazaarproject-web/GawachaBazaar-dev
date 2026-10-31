"""Read-through cache for the public catalog (categories, products, ads, home
slides, offers) on top of the route cache's Redis client, with in-process
fallback.

Invalidation is automatic and instant: every cache key embeds a catalog
*version*, and any committed write to a catalog or stock table bumps it (see
the SQLAlchemy listeners at the bottom), so admin edits, price changes and
stock movements from orders show up on the next request. The TTL is only a
backstop for time-based changes (a price or promotion becoming valid).

Never cached: anything per customer (cart, orders, wishlist, checkout
quotes) - prices and stock are re-validated by the backend at checkout.
Reliability: every Redis error is swallowed. If the version can't be read or
bumped, the cache is bypassed (straight to the database) until entries from
before the failure have expired, so it can never serve data older than the
last write.
"""

import json
import logging
import time
from collections.abc import Callable
from typing import Any

from pydantic import TypeAdapter
from sqlalchemy import event
from sqlalchemy.orm import Session

from app.core.config import settings
from app.services.routing.cache import RouteCache

logger = logging.getLogger(__name__)

_VERSION_KEY = "catalog:version"

# Tables whose writes change what the public catalog returns, directly or
# through price / stock / promotion rules.
WATCHED_TABLES = frozenset(
    {
        "categories",
        "products",
        "product_categories",
        "product_images",
        "product_variants",
        "prices",
        "inventory_lots",
        "inventory_reservations",
        "inventory_reservation_items",
        "stock_movements",
        "batches",
        "ads",
        "home_slides",
        "promotions",
        "promotion_targets",
        "promotion_eligible_customers",
    }
)


class CatalogCache:
    def __init__(self, store: RouteCache | None = None) -> None:
        self._store = store or RouteCache()
        self._local_version = 0
        self._bypass_until = 0.0

    def _version(self) -> str | None:
        """Version token for keys, or None when the cache must be bypassed."""
        if time.monotonic() < self._bypass_until:
            return None
        if self._store.is_shared:
            shared = self._store.get_int(_VERSION_KEY)
            if shared is None:
                self._bypass()
                return None
            return f"r{shared}"
        return f"l{self._local_version}"

    def _bypass(self) -> None:
        # Entries written before the failure can live at most TTL seconds.
        self._bypass_until = time.monotonic() + max(settings.CATALOG_CACHE_TTL_SECONDS, 1) + 5

    def bump(self) -> None:
        """Invalidate everything cached so far. Called after a catalog write commits."""
        self._local_version += 1
        # With Redis configured, a bump that can't reach it leaves the shared
        # version unchanged, so old entries must not be served after it recovers.
        if settings.REDIS_URL and not (self._store.is_shared and self._store.incr(_VERSION_KEY)):
            self._bypass()

    def get_or_load(
        self,
        namespace: str,
        params: dict[str, Any],
        response_type: Any,
        loader: Callable[[], Any],
        ttl: int | None = None,
    ) -> Any:
        ttl = settings.CATALOG_CACHE_TTL_SECONDS if ttl is None else ttl
        if ttl <= 0:
            return loader()
        adapter = TypeAdapter(response_type)
        version = self._version()
        if version is None:
            return loader()
        key = f"catalog:{version}:{namespace}:{json.dumps(params, sort_keys=True, default=str)}"
        try:
            hit = self._store.get(key)
            if hit is not None:
                return adapter.validate_python(hit["v"])
        except Exception:  # noqa: BLE001 - a bad payload is just a miss
            logger.warning("catalog_cache bad_entry namespace=%s", namespace)
        value = loader()
        try:
            self._store.set(key, {"v": adapter.dump_python(value, mode="json")}, ttl)
        except Exception:  # noqa: BLE001 - never fail a request over caching
            logger.warning("catalog_cache store_failed namespace=%s", namespace)
        return value


catalog_cache = CatalogCache()


# --- automatic invalidation -------------------------------------------------

_DIRTY = "catalog_cache_dirty"


@event.listens_for(Session, "after_flush")
def _flag_flushed_changes(session: Session, _ctx: Any) -> None:
    for obj in (*session.new, *session.dirty, *session.deleted):
        if getattr(obj, "__tablename__", None) in WATCHED_TABLES:
            session.info[_DIRTY] = True
            return


@event.listens_for(Session, "do_orm_execute")
def _flag_bulk_changes(state: Any) -> None:
    if not (state.is_update or state.is_delete or state.is_insert):
        return
    table = getattr(state.statement, "table", None)
    if getattr(table, "name", None) in WATCHED_TABLES:
        state.session.info[_DIRTY] = True


@event.listens_for(Session, "after_commit")
def _bump_after_commit(session: Session) -> None:
    if session.info.pop(_DIRTY, False):
        catalog_cache.bump()


@event.listens_for(Session, "after_rollback")
def _forget_after_rollback(session: Session) -> None:
    session.info.pop(_DIRTY, None)
