"""Shared current-price resolution, reused by Catalog, Cart, and Order services.

Extracted in Phase 13 to avoid duplicating this rule in three places
(catalog display, cart display, checkout snapshotting). Extracting it also
fixed a determinism gap in the original Phase 10 implementation: ties on
the exact same `valid_from` were broken by whatever row order PostgreSQL
happened to return, not by `id`. Phase 13 requires a deterministic
`id DESC` tie-break; this version provides it for every caller, including
CatalogService's public catalog display.
"""

from datetime import UTC, datetime

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.price import Price


def get_current_prices_for_variants(
    db: Session, variant_ids: list[int]
) -> dict[int, Price]:
    """Resolve the single current price per variant in one query (no N+1).

    Eligible: is_active AND valid_from <= now AND (valid_to IS NULL OR valid_to >= now).
    Tie-break: most recent valid_from wins; if multiple eligible rows share
    the exact same valid_from, the highest id wins (deterministic).
    """
    if not variant_ids:
        return {}

    now = datetime.now(UTC)
    rows = (
        db.query(Price)
        .filter(
            Price.variant_id.in_(variant_ids),
            Price.is_active.is_(True),
            Price.valid_from <= now,
            or_(Price.valid_to.is_(None), Price.valid_to >= now),
        )
        .order_by(Price.variant_id, Price.valid_from.desc(), Price.id.desc())
        .all()
    )
    current: dict[int, Price] = {}
    for row in rows:
        if row.variant_id not in current:
            current[row.variant_id] = row
    return current
