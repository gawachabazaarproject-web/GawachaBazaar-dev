"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { hasPermission, Permission } from "@/lib/permissions";
import { fetchAdminOrders } from "@/lib/orders";
import { fetchStockAlerts, StockAlerts } from "@/lib/inventory";
import { useOrderEvents } from "@/lib/realtime-context";
import { Icon, IconName } from "./icons";
import { GlobalSearch } from "./GlobalSearch";

interface NavItem {
  label: string;
  href: string;
  icon: IconName;
  /** Omitted = visible to anyone who can open the admin panel at all. */
  permission?: Permission;
  /** Page exists but is not built yet - shown last, with a "Soon" tag. */
  soon?: boolean;
  /** List page that understands `?q=` (used by the top-bar search). */
  searchable?: boolean;
}

const NAV_GROUPS: { title: string | null; items: NavItem[] }[] = [
  {
    title: null,
    items: [{ label: "Overview", href: "/dashboard", icon: "grid" }],
  },
  {
    title: "Sell",
    items: [
      { label: "Orders", href: "/orders", icon: "package", permission: "orders.read", searchable: true },
      { label: "Delivery", href: "/delivery", icon: "truck", permission: "delivery.read" },
      { label: "Payments", href: "/payments", icon: "credit-card", permission: "orders.refund", searchable: true },
      { label: "Customers", href: "/customers", icon: "users", permission: "customers.view", searchable: true },
    ],
  },
  {
    title: "Catalogue",
    items: [
      { label: "Products", href: "/products", icon: "tag", permission: "products.read", searchable: true },
      { label: "Categories", href: "/categories", icon: "box", permission: "categories.read", searchable: true },
      { label: "Inventory", href: "/inventory", icon: "box", permission: "inventory.read", searchable: true },
    ],
  },
  {
    title: "Marketing",
    items: [
      { label: "Promotions", href: "/promotions", icon: "megaphone", permission: "promotions.read", searchable: true },
      { label: "Home slides", href: "/content", icon: "file-text", permission: "ads.read" },
      { label: "Ads", href: "/ads", icon: "megaphone", permission: "ads.read" },
    ],
  },
  {
    title: "Administration",
    items: [
      { label: "Staff", href: "/staff", icon: "users", permission: "staff.read" },
      { label: "Settings", href: "/settings", icon: "settings", permission: "settings.manage" },
    ],
  },
  {
    title: "Coming soon",
    items: [
      { label: "Reviews", href: "/reviews", icon: "star", permission: "reviews.read", soon: true },
      { label: "Reports", href: "/reports", icon: "bar-chart", permission: "reports.read", soon: true },
      { label: "Audit Log", href: "/audit-log", icon: "shield", permission: "audit.read", soon: true },
    ],
  },
];

export function AdminShell({ children }: { children: React.ReactNode }) {
  const { user, logout, getAccessToken } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const [collapsed, setCollapsed] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const bellRef = useRef<HTMLDivElement>(null);

  const roles = user?.roles ?? [];
  const groups = NAV_GROUPS.map((g) => ({
    ...g,
    items: g.items.filter((item) => !item.permission || hasPermission(roles, item.permission)),
  })).filter((g) => g.items.length > 0);
  const allItems = groups.flatMap((g) => g.items);
  const searchPages = allItems.filter((i) => !i.soon).map(({ label, href, icon }) => ({ label, href, icon }));
  const searchable = allItems.filter((i) => i.searchable).map(({ label, href, icon }) => ({ label, href, icon }));
  const currentItem = allItems.find((i) => pathname === i.href || pathname?.startsWith(`${i.href}/`));
  const currentLabel = currentItem?.label;

  // Tab title follows the page, so several admin tabs are distinguishable.
  useEffect(() => {
    document.title = `${currentLabel ? `${currentLabel} | ` : ""}Gawacha Bazaar Admin`;
  }, [currentLabel]);

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
    setDrawerOpen(false);
  }, [pathname, refreshStock]);
  const alertCount = stockAlerts?.count ?? 0;
  useEffect(() => {
    if (alertCount < dismissedAt) setDismissedAt(alertCount);
  }, [alertCount, dismissedAt]);

  // Close the bell on outside click and Escape; Escape also closes the drawer.
  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (bellRef.current && !bellRef.current.contains(e.target as Node)) setBellOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setBellOpen(false);
        setDrawerOpen(false);
      }
    };
    window.addEventListener("mousedown", onClick);
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("mousedown", onClick);
      window.removeEventListener("keydown", onKey);
    };
  }, []);

  const badgeFor = (href: string) => (href === "/orders" ? pendingOrders : href === "/inventory" ? alertCount : 0);
  const badgeLabel = (href: string) => (href === "/inventory" ? "items need restocking" : "pending orders");

  const handleLogout = async () => {
    await logout();
    router.replace("/login");
  };

  const sidebar = (mobile: boolean) => {
    const slim = collapsed && !mobile;
    return (
      <div className="flex h-full flex-col">
        <div className="flex h-16 shrink-0 items-center justify-between border-b border-primary-700 px-4">
          {!slim && (
            <Link href="/dashboard" className="leading-tight">
              <p className="font-display text-lg font-semibold text-white">Gawacha</p>
              <p className="eyebrow text-secondary-300">Bazaar</p>
            </Link>
          )}
          {mobile ? (
            <button
              onClick={() => setDrawerOpen(false)}
              className="rounded p-1.5 text-neutral-300 hover:bg-primary-700 hover:text-white"
              aria-label="Close menu"
            >
              <Icon name="x" size={18} />
            </button>
          ) : (
            <button
              onClick={() => setCollapsed((c) => !c)}
              className="rounded p-1.5 text-neutral-300 hover:bg-primary-700 hover:text-white"
              aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            >
              <Icon name="chevron-left" size={16} className={collapsed ? "rotate-180" : ""} />
            </button>
          )}
        </div>

        <nav aria-label="Main" className="flex-1 overflow-y-auto p-2">
          {groups.map((group, gi) => (
            <div key={group.title ?? gi} className={gi === 0 ? "" : "mt-3"}>
              {group.title && !slim && (
                <p className="px-3 pb-1 pt-1 text-[10px] font-semibold uppercase tracking-widest text-primary-300">
                  {group.title}
                </p>
              )}
              {group.title && slim && <div className="mx-3 mb-2 border-t border-primary-700" />}
              <div className="flex flex-col gap-0.5">
                {group.items.map((item) => {
                  const active = pathname === item.href || pathname?.startsWith(`${item.href}/`);
                  const badge = badgeFor(item.href);
                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      aria-current={active ? "page" : undefined}
                      className={`flex items-center gap-3 rounded px-3 py-2 text-sm font-medium transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-secondary-300 ${
                        active
                          ? "bg-primary-700 text-white"
                          : item.soon
                            ? "text-neutral-400 hover:bg-primary-700/60 hover:text-white"
                            : "text-neutral-300 hover:bg-primary-700/60 hover:text-white"
                      }`}
                      title={slim ? item.label : undefined}
                    >
                      <span className="relative">
                        <Icon name={item.icon} size={17} />
                        {slim && badge > 0 && (
                          <span className="absolute -right-1.5 -top-1.5 h-2.5 w-2.5 rounded-full bg-secondary-400" />
                        )}
                      </span>
                      {!slim && <span className="flex-1">{item.label}</span>}
                      {!slim && item.soon && (
                        <span className="rounded bg-primary-700 px-1.5 py-0.5 text-[10px] font-semibold uppercase text-neutral-300">
                          Soon
                        </span>
                      )}
                      {!slim && badge > 0 && (
                        <span
                          className={`min-w-[22px] rounded-full px-1.5 py-0.5 text-center text-xs font-bold ${
                            item.href === "/inventory" ? "bg-status-danger text-white" : "bg-secondary-400 text-primary-900"
                          }`}
                          aria-label={`${badge} ${badgeLabel(item.href)}`}
                        >
                          {badge > 99 ? "99+" : badge}
                        </span>
                      )}
                    </Link>
                  );
                })}
              </div>
            </div>
          ))}
        </nav>

        <div className="shrink-0 border-t border-primary-700 p-3">
          {!slim && user && (
            <div className="mb-2 px-1">
              <p className="truncate text-sm font-medium text-white">{user.name}</p>
              <p className="truncate text-xs text-neutral-400">{user.roles.join(", ")}</p>
            </div>
          )}
          <button
            onClick={handleLogout}
            className="flex w-full items-center gap-2 rounded px-3 py-2 text-sm font-medium text-neutral-300 hover:bg-primary-700/60 hover:text-white"
            title={slim ? "Log out" : undefined}
          >
            <Icon name="log-out" size={16} />
            {!slim && <span>Log out</span>}
          </button>
        </div>
      </div>
    );
  };

  return (
    <div className="flex min-h-screen bg-neutral-100">
      <a
        href="#main-content"
        className="sr-only z-50 rounded bg-white px-3 py-2 text-sm font-semibold text-primary-800 focus:not-sr-only focus:fixed focus:left-3 focus:top-3"
      >
        Skip to content
      </a>

      <aside
        className={`sticky top-0 hidden h-screen shrink-0 border-r border-neutral-200 bg-primary-800 text-neutral-100 transition-all duration-200 lg:block ${
          collapsed ? "w-[68px]" : "w-64"
        }`}
      >
        {sidebar(false)}
      </aside>

      {drawerOpen && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div className="absolute inset-0 bg-black/50" onClick={() => setDrawerOpen(false)} aria-hidden="true" />
          <aside className="absolute inset-y-0 left-0 w-72 max-w-[85vw] bg-primary-800 text-neutral-100 shadow-xl">
            {sidebar(true)}
          </aside>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-16 items-center justify-between gap-3 border-b border-neutral-200 bg-white px-4 sm:px-6">
          <div className="flex min-w-0 flex-1 items-center gap-2">
            <button
              onClick={() => setDrawerOpen(true)}
              className="rounded p-2 text-neutral-600 hover:bg-neutral-100 lg:hidden"
              aria-label="Open menu"
            >
              <Icon name="menu" size={20} />
            </button>
            <GlobalSearch pages={searchPages} searchable={searchable} />
          </div>
          <div className="flex shrink-0 items-center gap-3 sm:gap-4">
            <div className="relative" ref={bellRef}>
              <button
                onClick={() => setBellOpen((o) => !o)}
                className="relative rounded p-2 text-neutral-500 hover:bg-neutral-100"
                aria-label={alertCount > 0 ? `Notifications - ${alertCount} stock alert${alertCount === 1 ? "" : "s"}` : "Notifications"}
                aria-expanded={bellOpen}
              >
                <Icon name="bell" size={18} />
                {alertCount > 0 && (
                  <span className="absolute -right-0.5 -top-0.5 min-w-[18px] rounded-full bg-status-danger px-1 text-center text-[10px] font-bold leading-[18px] text-white">
                    {alertCount > 9 ? "9+" : alertCount}
                  </span>
                )}
              </button>
              {bellOpen && (
                <div className="absolute right-0 top-11 z-40 w-[min(20rem,calc(100vw-2rem))] rounded border border-neutral-200 bg-white p-3 shadow-xl">
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
            <div className="flex items-center gap-2 border-l border-neutral-200 pl-3 sm:pl-4">
              <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary-100 text-primary-800">
                <Icon name="user" size={16} />
              </div>
              {user && (
                <div className="hidden leading-tight sm:block">
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
            className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 border-b border-status-warning/30 bg-status-warningLight px-4 py-2.5 text-sm text-primary-900 sm:px-6"
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

        <main id="main-content" className="flex-1 p-4 sm:p-6">
          {children}
        </main>
      </div>
    </div>
  );
}
