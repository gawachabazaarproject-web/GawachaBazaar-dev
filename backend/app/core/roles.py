"""Canonical baseline role names for RBAC.

`roles.name` in the database is the authoritative record of which roles exist.
This module is the single in-code representation of those six active role
names, so application code never scatters raw role-name string literals.

Farmer/Farm are future capabilities and intentionally have no role here.
"""

CUSTOMER = "CUSTOMER"
WHOLESALER = "WHOLESALER"
ADMIN = "ADMIN"
HUB_STAFF = "HUB_STAFF"
OPERATIONS = "OPERATIONS"
DELIVERY_PARTNER = "DELIVERY_PARTNER"

BASELINE_ROLES: tuple[str, ...] = (
    CUSTOMER,
    WHOLESALER,
    ADMIN,
    HUB_STAFF,
    OPERATIONS,
    DELIVERY_PARTNER,
)
