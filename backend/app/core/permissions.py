"""Granular permission strings for the admin panel, layered on top of the
existing coarse role system (`app/core/roles.py`).

This is deliberately NOT a new database-backed permission system. There is
no `permissions` or `role_permissions` table. `ROLE_PERMISSIONS` below is a
static, in-code mapping from an existing role name to the set of granular
actions that role may perform - reviewed and versioned like any other code,
enforced the same way `require_roles` already is (checked against live
`user_roles` on every request, never cached in the JWT).

Every permission this module grants must already be true of the domain it
names, or be a placeholder for a domain that does not exist yet (reviews,
promotions, audit, settings - see the Phase 1 architecture audit). Adding a
permission here does not, by itself, open up any capability: a route only
becomes reachable once it is actually gated with `require_permission(...)`
(see `app/dependencies/auth.py`), which happens as each admin module is
built. Until then these entries are inert.

Only staff roles participate (ADMIN, OPERATIONS, HUB_STAFF,
DELIVERY_PARTNER, SUPPORT) - CUSTOMER and WHOLESALER never open the admin
panel and are intentionally absent from this map.
"""

from app.core.roles import ADMIN, DELIVERY_PARTNER, HUB_STAFF, OPERATIONS, SUPPORT

# Catalog - matches catalog.py, which currently gates every mutation with
# `require_roles(ADMIN)` only (no OPERATIONS/HUB_STAFF override exists yet).
# `manage_media`/`manage_pricing` are split out from `products.update`
# because image and price mutations are their own endpoints
# (POST/PATCH/DELETE .../images, POST/PATCH .../prices) with their own
# business rules (single-primary-image invariant, price-history
# preservation) - a role could plausibly manage one without the other.
# There is no `products.manage_merchandising` yet: the backend has no
# featured/seasonal fields to gate (see the Phase 1 admin-panel audit), so
# a permission string for it would be inert by construction, not just by
# policy - it will be added alongside that backend work, not before it.
CATALOG_PERMISSIONS = {
    "products.read",
    "products.create",
    "products.update",
    "products.delete",
    "products.manage_media",
    "products.manage_pricing",
    "categories.read",
    "categories.create",
    "categories.update",
    "categories.delete",
}

# Inventory - matches inventory.py's router-level
# `require_roles(ADMIN, HUB_STAFF, OPERATIONS)`; the backend does not yet
# distinguish read from write access within most of that file, so neither
# does this. `receive`/`reconcile` were added alongside the admin-panel
# Inventory module's new POST /inventory/admin/{receive,lots/{id}/reconcile}
# endpoints - same three roles as everything else in this domain, since
# nothing in the existing router distinguishes them for any inventory
# action today.
INVENTORY_PERMISSIONS = {
    "inventory.read",
    "inventory.adjust",
    "inventory.transfer",
    "inventory.receive",
    "inventory.reconcile",
}

# Orders - matches orders.py's admin_router, which only exposes
# `POST /admin/{order_id}/cancel` gated `require_roles(ADMIN)`. There is no
# admin-wide order list/detail endpoint yet (Phase 1 finding) - orders.read
# here anticipates that endpoint, not something already reachable.
ORDER_PERMISSIONS = {
    "orders.read",
    "orders.update",
    "orders.cancel",
}

# Refunds - matches payments.py's admin_router, which is explicitly
# ADMIN-only by design (its module docstring calls out that OPERATIONS and
# HUB_STAFF are deliberately excluded from refund approval).
REFUND_PERMISSIONS = {
    "orders.refund",
}

# Reviews - the domain does not exist in the backend yet (Phase 1 finding:
# no Review model, no endpoints). These strings exist so the admin
# frontend's permission model is stable across the phase that adds it;
# until then nothing enforces or grants any actual capability.
REVIEW_PERMISSIONS = {
    "reviews.read",
    "reviews.moderate",
}

# Promotions - matches promotions.py's admin_router. Kept ADMIN-only (no
# OPERATIONS/HUB_STAFF grant below), same precedent as REFUND_PERMISSIONS:
# discount rules are a pricing/financial lever, not an operations task.
# `promotions.manage_status` covers activate/pause/disable/archive/duplicate
# (all state-transition actions on an existing promotion); `create`/`update`
# cover the multi-section create/edit form.
PROMOTION_PERMISSIONS = {
    "promotions.read",
    "promotions.create",
    "promotions.update",
    "promotions.manage_status",
}

# Customers - matches customers.py's admin_router. A "customer" is an
# existing User holding the CUSTOMER role, not a separate table - see
# app/services/customer.py. `customers.view` is plain read (list/detail/
# orders/promotions/addresses/timeline, phone masked) and is the only one of
# these granted to the read-only SUPPORT role below; everything else
# (`view_sensitive`, `manage_status`, `notes`, `manage_contact`) stays
# ADMIN-only, same precedent as Promotions/Refunds - customer PII, account-
# status changes, and identity (email/phone) changes are at least as
# sensitive as a discount rule. `manage_contact` gates the verification-
# backed email/phone change workflow (see app/services/contact_change.py) -
# kept separate from `manage_status` because it is a different, higher-
# stakes capability (changing login identity, not just enable/disable).
CUSTOMER_PERMISSIONS = {
    "customers.view",
    "customers.view_sensitive",
    "customers.manage_status",
    "customers.notes",
    "customers.manage_contact",
}

# Delivery - matches fulfillments.py. `delivery.read` mirrors the 4-role GET
# group (ADMIN, HUB_STAFF, OPERATIONS, DELIVERY_PARTNER, each partner scoped
# to their own by the service layer). `delivery.assign` mirrors the
# assign/advance-status routes (ADMIN, HUB_STAFF, OPERATIONS only).
# `delivery.fulfill` mirrors out-for-delivery/deliver (ADMIN,
# DELIVERY_PARTNER only) - kept distinct from `delivery.assign` because a
# delivery partner may fulfil their own assignment but must never be able
# to assign one to themselves or anyone else.
DELIVERY_PERMISSIONS = {
    "delivery.read",
    "delivery.assign",
    "delivery.fulfill",
}

# Reports/analytics - read-only, computed from existing authoritative data.
REPORT_PERMISSIONS = {
    "reports.read",
}

# Settings - no DB-backed settings domain exists yet (Phase 1 finding:
# `Settings` today is only env-driven app config, not admin-editable).
SETTINGS_PERMISSIONS = {
    "settings.manage",
}

# Audit - no general-purpose audit log exists yet (Phase 1 finding). The
# closest analog today is StockMovement (inventory-only) and the
# cancellation/refund audit columns already on Order/Refund.
AUDIT_PERMISSIONS = {
    "audit.read",
}

ALL_PERMISSIONS: frozenset[str] = frozenset(
    CATALOG_PERMISSIONS
    | INVENTORY_PERMISSIONS
    | ORDER_PERMISSIONS
    | REFUND_PERMISSIONS
    | REVIEW_PERMISSIONS
    | PROMOTION_PERMISSIONS
    | CUSTOMER_PERMISSIONS
    | DELIVERY_PERMISSIONS
    | REPORT_PERMISSIONS
    | SETTINGS_PERMISSIONS
    | AUDIT_PERMISSIONS
)

# ADMIN is the top role until a dedicated SUPER_ADMIN role is introduced
# (explicitly deferred - see the admin-panel Phase 1/2 decision): it holds
# every permission this module defines, including the domains that don't
# have a backend yet, so the admin frontend can already reason about "what
# could an ADMIN eventually do here" without a second migration later.
ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    ADMIN: ALL_PERMISSIONS,
    OPERATIONS: frozenset(
        INVENTORY_PERMISSIONS
        | {"orders.read"}
        | DELIVERY_PERMISSIONS
        | REPORT_PERMISSIONS
    ),
    HUB_STAFF: frozenset(
        INVENTORY_PERMISSIONS
        | {"orders.read", "delivery.read", "delivery.assign"}
    ),
    DELIVERY_PARTNER: frozenset({"delivery.read", "delivery.fulfill"}),
    # Read-only customer-support agent - can look up a customer's profile,
    # orders, promotions, addresses, and timeline to answer "who is this
    # customer and what happened with their order", but cannot see the
    # unmasked phone number, change account status, write notes, or touch
    # email/phone (all of those stay ADMIN-only).
    SUPPORT: frozenset({"customers.view"}),
}


def role_has_permission(role_names: list[str], permission: str) -> bool:
    """True if any of the given role names grants `permission`."""
    return any(permission in ROLE_PERMISSIONS.get(role, frozenset()) for role in role_names)
