"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { hasPermission, Permission } from "@/lib/permissions";
import { fetchAdminOrders } from "@/lib/orders";
import { fetchStockAlerts, StockAlerts } from "@/lib/inventory";
import { useOrderEvents } from "@/lib/realtime-context";
import { Icon, IconName } from "./icons";

interface NavItem {
  label: string;
  href: string;
  icon: IconName;
  /** Omitted = visible to anyone who can open the admin panel at all. */
  permission?: Permission;
}

const NAV_ITEMS: NavItem[] = [
  { label: "Overview", href: "/dashboard", icon: "grid" },
  { label: "Orders", href: "/orders", icon: "package", permission: "orders.read" },
  { label: "Products", href: "/products", icon: "tag", permission: "products.read" },
  { label: "Categories", href: "/categories", icon: "box", permission: "categories.read" },
  { label: "Inventory", href: "/inventory", icon: "box", permission: "inventory.read" },
  { label: "Promotions", href: "/promotions", icon: "megaphone", permission: "promotions.read" },
  { label: "Customers", href: "/customers", icon: "users", permission: "customers.view" },
  { label: "Reviews", href: "/reviews", icon: "star", permission: "reviews.read" },
  { label: "Delivery", href: "/delivery", icon: "truck", permission: "delivery.read" },
  { label: "Payments", href: "/payments", icon: "credit-card", permission: "orders.refund" },
  { label: "Reports", href: "/reports", icon: "bar-chart", permission: "reports.read" },
  { label: "Home slides", href: "/content", icon: "file-text", permission: "ads.read" },
  { label: "Settings", href: "/settings", icon: "settings", permission: "settings.manage" },
  { label: "Audit Log", href: "/audit-log", icon: "shield", permission: "audit.read" },
  { label: "Staff", href: "/staff", icon: "users", permission: "staff.read" },
  { label: "Ads", href: "/ads", icon: "megaphone", permission: "ads.read" },
];

export function AdminShell({ children }: { children: React.ReactNode }) {
  const { user, logout, getAccessToken } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const [collapsed, setCollapsed] = useState(false);

  const roles = user?.roles ?? [];
  const visibleItems = NAV_ITEMS.filter((item) => !item.permission || hasPermission(roles, item.permission));

  // Orders still waiting to be confirmed - the number staff need to act on.
  const canSeeOrders = hasPermission(roles, "orders.read");
  const [pendingOrders, setPendingOrders] = useState(0);
  const refreshPending = useCallback(() => {
    const token = getAccessToken();
    if (!token || !canSeeOrders) return;
    fetchAdminOrders(token, { status: "PENDING", page: 1, page_size: 1 })
      .then((r) => setPendingOrders(r.total))
      .catch(() => undefined);
  }, [getAccessToken, canSeeOrders]);
  useEffect(() => {
    refreshPending();
    const timer = window.setInterval(refreshPending, 60_000);
    return () => window.clearInterval(timer);
  }, [refreshPending]);
  // New orders and every status change arrive live over the websocket.
  useOrderEvents((event) => {
    if (event.resource === "order") refreshPending();
  });

  // Items that are out of stock, at/below their reserve level, or close to it.
  // Polled every minute and re-checked after every page change, so a restock
  // (or a sale that drains an item) shows up without a refresh.
  const canSeeInventory = hasPermission(roles, "inventory.read");
  const [stockAlerts, setStockAlerts] = useState<StockAlerts | null>(null);
  const [bellOpen, setBellOpen] = useState(false);
  // Banner dismissal holds until the number of alerts goes up again.
  const [dismissedAt, setDismissedAt] = useState(0);
  const refreshStock = useCallback(() => {
    const token = getAccessToken();
    if (!token || !canSeeInventory) return;
    fetchStockAlerts(token)
      .then(setStockAlerts)
      .catch(() => undefined);
  }, [getAccessToken, canSeeInventory]);
  useEffect(() => {
    refreshStock();
    const timer = window.setInterval(refreshStock, 60_000);
    return () => window.clearInterval(timer);
  }, [refreshStock]);
  useEffect(() => {
    refreshStock();
    setBellOpen(false);
  }, [pathname, refreshStock]);
  const alertCount = stockAlerts?.count ?? 0;
  useEffect(() => {
    if (alertCount < dismissedAt) setDismissedAt(alertCount);
  }, [alertCount, dismissedAt]);

  const badgeFor = (href: string) => (href === "/orders" ? pendingOrders : href === "/inventory" ? alertCount : 0);
  const badgeLabel = (href: string) => (href === "/inventory" ? "items need restocking" : "pending orders");

  const handleLogout = async () => {
    await logout();
    router.replace("/login");
  };

  return (
    <div className="flex min-h-screen bg-neutral-100">
      <aside
        className={`shrink-0 border-r border-neutral-200 bg-primary-800 text-neutral-100 transition-all duration-200 ${
          collapsed ? "w-[68px]" : "w-64"
        }`}
      >
        <div className="flex h-16 items-center justify-between border-b border-primary-700 px-4">
          {!collapsed && (
            <div className="leading-tight">
              <p className="font-display text-lg font-semibold text-white">Gawacha</p>
              <p className="eyebrow text-secondary-300">Bazaar</p>
            </div>
          )}
          <button
            onClick={() => setCollapsed((c) => !c)}
            className="rounded p-1.5 text-neutral-300 hover:bg-primary-700 hover:text-white"
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            <Icon name="chevron-left" size={16} className={collapsed ? "rotate-180" : ""} />
          </button>
        </div>

        <nav className="flex flex-col gap-0.5 p-2">
          {visibleItems.map((item) => {
            const active = pathname === item.href || pathname?.startsWith(`${item.href}/`);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center gap-3 rounded px-3 py-2 text-sm font-medium transition-colors ${
                  active
                    ? "bg-primary-700 text-white"
                    : "text-neutral-300 hover:bg-primary-700/60 hover:text-white"
                }`}
                title={collapsed ? item.label : undefined}
              >
                <span className="relative">
                  <Icon name={item.icon} size={17} />
                  {collapsed && badgeFor(item.href) > 0 && (
                    <span className="absolute -right-1.5 -top-1.5 h-2.5 w-2.5 rounded-full bg-secondary-400" />
                  )}
                </span>
                {!collapsed && <span className="flex-1">{item.label}</span>}
                {!collapsed && badgeFor(item.href) > 0 && (
                  <span
                    className={`min-w-[22px] rounded-full px-1.5 py-0.5 text-center text-xs font-bold ${
                      item.href === "/inventory" ? "bg-status-danger text-white" : "bg-secondary-400 text-primary-900"
                    }`}
                    aria-label={`${badgeFor(item.href)} ${badgeLabel(item.href)}`}
                  >
                    {badgeFor(item.href) > 99 ? "99+" : badgeFor(item.href)}
                  </span>
                )}
              </Link>
            );
          })}
        </nav>

        <div className="mt-auto border-t border-primary-700 p-3">
          {!collapsed && user && (
            <div className="mb-2 px-1">
              <p className="truncate text-sm font-medium text-white">{user.name}</p>
              <p className="truncate text-xs text-neutral-400">{user.roles.join(", ")}</p>
            </div>
          )}
          <button
            onClick={handleLogout}
            className="flex w-full items-center gap-2 rounded px-3 py-2 text-sm font-medium text-neutral-300 hover:bg-primary-700/60 hover:text-white"
          >
            <Icon name="log-out" size={16} />
            {!collapsed && <span>Log out</span>}
          </button>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-16 items-center justify-between border-b border-neutral-200 bg-white px-6">
          <div className="flex max-w-md flex-1 items-center gap-2 rounded border border-neutral-200 bg-neutral-50 px-3 py-2 text-sm text-neutral-500">
            <Icon name="search" size={16} />
            <span>Search orders, products, customers...</span>
          </div>
          <div className="flex items-center gap-4">
            <div className="relative">
              <button
                onClick={() => setBellOpen((o) => !o)}
                className="relative rounded p-2 text-neutral-500 hover:bg-neutral-100"
                aria-label={alertCount > 0 ? `Notifications - ${alertCount} stock alert${alertCount === 1 ? "" : "s"}` : "Notifications"}
              >
                <Icon name="bell" size={18} />
                {alertCount > 0 && (
                  <span className="absolute -right-0.5 -top-0.5 min-w-[18px] rounded-full bg-status-danger px-1 text-center text-[10px] font-bold leading-[18px] text-white">
                    {alertCount > 9 ? "9+" : alertCount}
                  </span>
                )}
              </button>
              {bellOpen && (
                <div className="absolute right-0 top-11 z-40 w-80 rounded border border-neutral-200 bg-white p-3 shadow-xl">
                  <p className="mb-2 font-display text-sm font-semibold text-primary-900">Stock alerts</p>
                  {!stockAlerts || stockAlerts.count === 0 ? (
                    <p className="py-4 text-center text-sm text-neutral-500">Everything is comfortably above its reserve.</p>
                  ) : (
                    <ul className="max-h-72 divide-y divide-neutral-100 overflow-y-auto">
                      {stockAlerts.items.map((a) => (
                        <li key={a.variant_id}>
                          <Link
                            href={`/products/${a.product_id}`}
                            className="flex items-center justify-between gap-2 py-2 text-sm hover:bg-neutral-50"
                          >
                            <span className="min-w-0">
                              <span className="block truncate font-medium text-primary-900">{a.product_name}</span>
                              <span className="block text-xs text-neutral-500">
                                {a.variant_name} · reserve {Number(a.reserve_level)} {a.unit}
                              </span>
                            </span>
                            <span
                              className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-semibold ${
                                a.level === "OUT"
                                  ? "bg-status-dangerLight text-status-danger"
                                  : a.level === "BELOW"
                                    ? "bg-status-warningLight text-status-warning"
                                    : "bg-neutral-100 text-neutral-600"
                              }`}
                            >
                              {a.level === "OUT" ? "Out" : `${Number(a.available)} left`}
                            </span>
                          </Link>
                        </li>
                      ))}
                    </ul>
                  )}
                  <Link href="/inventory" className="mt-2 block text-xs font-semibold text-primary-700 hover:underline">
                    Open inventory →
                  </Link>
                </div>
              )}
            </div>
            <div className="flex items-center gap-2 border-l border-neutral-200 pl-4">
              <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary-100 text-primary-800">
                <Icon name="user" size={16} />
              </div>
              {user && (
                <div className="leading-tight">
                  <p className="text-sm font-medium text-primary-900">{user.name}</p>
                  <p className="text-xs text-neutral-500">{user.roles[0]}</p>
                </div>
              )}
            </div>
          </div>
        </header>

        {stockAlerts && alertCount > 0 && alertCount > dismissedAt && (
          <div
            role="alert"
            className="flex items-center justify-between gap-4 border-b border-status-warning/30 bg-status-warningLight px-6 py-2.5 text-sm text-primary-900"
          >
            <p>
              <strong>
                {alertCount} item{alertCount === 1 ? " needs" : "s need"} restocking
              </strong>
              {" - "}
              {[
                stockAlerts.out_count > 0 ? `${stockAlerts.out_count} out of stock` : null,
                stockAlerts.below_count > 0 ? `${stockAlerts.below_count} at or below reserve` : null,
                stockAlerts.near_count > 0 ? `${stockAlerts.near_count} close to reserve` : null,
              ]
                .filter(Boolean)
                .join(", ")}
              .
            </p>
            <div className="flex shrink-0 items-center gap-3">
              <Link href="/dashboard" className="font-semibold text-primary-800 hover:underline">
                See which
              </Link>
              <Link href="/inventory" className="font-semibold text-primary-800 hover:underline">
                Inventory
              </Link>
              <button
                onClick={() => setDismissedAt(alertCount)}
                className="rounded px-1.5 text-lg leading-none text-neutral-500 hover:bg-white/60"
                aria-label="Dismiss until more items run low"
              >
                ×
              </button>
            </div>
          </div>
        )}

        <main className="flex-1 overflow-y-auto p-6">{children}</main>
      </div>
    </div>
  );
}
