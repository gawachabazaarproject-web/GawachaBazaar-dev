"use client";

import React, { useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { hasPermission, Permission } from "@/lib/permissions";
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
  { label: "Content", href: "/content", icon: "file-text", permission: "promotions.read" },
  { label: "Settings", href: "/settings", icon: "settings", permission: "settings.manage" },
  { label: "Audit Log", href: "/audit-log", icon: "shield", permission: "audit.read" },
];

export function AdminShell({ children }: { children: React.ReactNode }) {
  const { user, logout } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const [collapsed, setCollapsed] = useState(false);

  const roles = user?.roles ?? [];
  const visibleItems = NAV_ITEMS.filter((item) => !item.permission || hasPermission(roles, item.permission));

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
                <Icon name={item.icon} size={17} />
                {!collapsed && <span>{item.label}</span>}
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
            <button
              className="rounded p-2 text-neutral-500 hover:bg-neutral-100"
              aria-label="Notifications"
            >
              <Icon name="bell" size={18} />
            </button>
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

        <main className="flex-1 overflow-y-auto p-6">{children}</main>
      </div>
    </div>
  );
}
