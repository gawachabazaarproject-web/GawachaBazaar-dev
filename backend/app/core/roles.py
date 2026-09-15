"""Canonical baseline role names for RBAC.

`roles.name` in the database is the authoritative record of which roles exist.
This module is the single in-code representation of those active role
names, so application code never scatters raw role-name string literals.

Farmer/Farm are future capabilities and intentionally have no role here.
"""

CUSTOMER = "CUSTOMER"
WHOLESALER = "WHOLESALER"
ADMIN = "ADMIN"
HUB_STAFF = "HUB_STAFF"
OPERATIONS = "OPERATIONS"
DELIVERY_PARTNER = "DELIVERY_PARTNER"
SUPPORT = "SUPPORT"

BASELINE_ROLES: tuple[str, ...] = (
    CUSTOMER,
    WHOLESALER,
    ADMIN,
    HUB_STAFF,
    OPERATIONS,
    DELIVERY_PARTNER,
    SUPPORT,
)

# Admin-panel roles - used by AuthService.authenticate() to decide who
# skips the login email-OTP second factor. Staff sign in from a controlled
# operations context (the Admin panel) and are a much smaller, vetted
# population than the open customer base, so this codebase treats them
# differently rather than adding OTP friction with no corresponding risk
# reduction. CUSTOMER and WHOLESALER are deliberately absent - both are
# open self-registration account types and both require the OTP step.
STAFF_ROLES: frozenset[str] = frozenset(
    {ADMIN, HUB_STAFF, OPERATIONS, DELIVERY_PARTNER, SUPPORT}
)
