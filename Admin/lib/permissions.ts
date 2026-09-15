/**
 * Mirrors backend/app/core/permissions.py exactly. This copy exists ONLY
 * to decide what the sidebar/UI shows - it grants nothing. Every mutation
 * still goes through the backend, which re-checks the same permission
 * against live role data on every request via `require_permission(...)`.
 * If the two drift, the backend wins; a user who bypasses a hidden button
 * still gets a 403 from the API.
 *
 * Keep this in sync by hand whenever backend/app/core/permissions.py
 * changes - there is no shared package between the two apps.
 */

export const ADMIN = "ADMIN";
export const OPERATIONS = "OPERATIONS";
export const HUB_STAFF = "HUB_STAFF";
export const DELIVERY_PARTNER = "DELIVERY_PARTNER";
export const SUPPORT = "SUPPORT";

const CATALOG_PERMISSIONS = [
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
] as const;

const INVENTORY_PERMISSIONS = [
  "inventory.read",
  "inventory.adjust",
  "inventory.transfer",
  "inventory.receive",
  "inventory.reconcile",
] as const;
const ORDER_PERMISSIONS = ["orders.read", "orders.update", "orders.cancel"] as const;
const REFUND_PERMISSIONS = ["orders.refund"] as const;
const REVIEW_PERMISSIONS = ["reviews.read", "reviews.moderate"] as const;
const PROMOTION_PERMISSIONS = [
  "promotions.read",
  "promotions.create",
  "promotions.update",
  "promotions.manage_status",
] as const;
const CUSTOMER_PERMISSIONS = [
  "customers.view",
  "customers.view_sensitive",
  "customers.manage_status",
  "customers.notes",
  "customers.manage_contact",
] as const;
const DELIVERY_PERMISSIONS = ["delivery.read", "delivery.assign", "delivery.fulfill"] as const;
const REPORT_PERMISSIONS = ["reports.read"] as const;
const SETTINGS_PERMISSIONS = ["settings.manage"] as const;
const AUDIT_PERMISSIONS = ["audit.read"] as const;

export type Permission =
  | (typeof CATALOG_PERMISSIONS)[number]
  | (typeof INVENTORY_PERMISSIONS)[number]
  | (typeof ORDER_PERMISSIONS)[number]
  | (typeof REFUND_PERMISSIONS)[number]
  | (typeof REVIEW_PERMISSIONS)[number]
  | (typeof PROMOTION_PERMISSIONS)[number]
  | (typeof CUSTOMER_PERMISSIONS)[number]
  | (typeof DELIVERY_PERMISSIONS)[number]
  | (typeof REPORT_PERMISSIONS)[number]
  | (typeof SETTINGS_PERMISSIONS)[number]
  | (typeof AUDIT_PERMISSIONS)[number];

const ALL_PERMISSIONS: Permission[] = [
  ...CATALOG_PERMISSIONS,
  ...INVENTORY_PERMISSIONS,
  ...ORDER_PERMISSIONS,
  ...REFUND_PERMISSIONS,
  ...REVIEW_PERMISSIONS,
  ...PROMOTION_PERMISSIONS,
  ...CUSTOMER_PERMISSIONS,
  ...DELIVERY_PERMISSIONS,
  ...REPORT_PERMISSIONS,
  ...SETTINGS_PERMISSIONS,
  ...AUDIT_PERMISSIONS,
];

const ROLE_PERMISSIONS: Record<string, Permission[]> = {
  [ADMIN]: ALL_PERMISSIONS,
  [OPERATIONS]: [
    ...INVENTORY_PERMISSIONS,
    "orders.read",
    ...DELIVERY_PERMISSIONS,
    ...REPORT_PERMISSIONS,
  ],
  [HUB_STAFF]: [...INVENTORY_PERMISSIONS, "orders.read", "delivery.read", "delivery.assign"],
  [DELIVERY_PARTNER]: ["delivery.read", "delivery.fulfill"],
  [SUPPORT]: ["customers.view"],
};

/** The only roles that may open the admin panel at all. */
export const ADMIN_PANEL_ROLES = [ADMIN, OPERATIONS, HUB_STAFF, DELIVERY_PARTNER, SUPPORT];

export function hasPermission(roles: string[], permission: Permission): boolean {
  return roles.some((role) => ROLE_PERMISSIONS[role]?.includes(permission));
}

export function canOpenAdminPanel(roles: string[]): boolean {
  return roles.some((role) => ADMIN_PANEL_ROLES.includes(role));
}
