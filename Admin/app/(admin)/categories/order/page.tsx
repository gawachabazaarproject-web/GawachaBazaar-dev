"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import { hasPermission } from "@/lib/permissions";
import {
  AdminCategoryListItem,
  CategoryApiError,
  fetchAdminCategories,
  reorderCategories,
} from "@/lib/categories";
import { PageHeader } from "@/components/PageHeader";
import { ErrorState } from "@/components/ErrorState";
import { TableSkeleton } from "@/components/TableSkeleton";

/** One reorderable list of siblings: drag a row by its handle, or use the
 * top/up/down/bottom buttons. The parent keeps the order in state; "Save order" sends it. */
function OrderList({
  items,
  disabled,
  onChange,
}: {
  items: AdminCategoryListItem[];
  disabled: boolean;
  onChange: (next: AdminCategoryListItem[]) => void;
}) {
  const [dragIndex, setDragIndex] = useState<number | null>(null);
  const [overIndex, setOverIndex] = useState<number | null>(null);

  const move = (from: number, to: number) => {
    if (to < 0 || to >= items.length || from === to) return;
    const next = [...items];
    const [row] = next.splice(from, 1);
    next.splice(to, 0, row);
    onChange(next);
  };

  return (
    <ul className="divide-y divide-neutral-100">
      {items.map((item, i) => {
        const buttons: [string, string, () => void, boolean][] = [
          ["⇈", "Move to top", () => move(i, 0), i === 0],
          ["↑", "Move up", () => move(i, i - 1), i === 0],
          ["↓", "Move down", () => move(i, i + 1), i === items.length - 1],
          ["⇊", "Move to bottom", () => move(i, items.length - 1), i === items.length - 1],
        ];
        const isTarget = overIndex === i && dragIndex !== null && dragIndex !== i;
        return (
          <li
            key={item.id}
            draggable={!disabled}
            onDragStart={(e) => {
              setDragIndex(i);
              e.dataTransfer.effectAllowed = "move";
            }}
            onDragOver={(e) => {
              e.preventDefault();
              if (overIndex !== i) setOverIndex(i);
            }}
            onDrop={(e) => {
              e.preventDefault();
              if (dragIndex !== null) move(dragIndex, i);
              setDragIndex(null);
              setOverIndex(null);
            }}
            onDragEnd={() => {
              setDragIndex(null);
              setOverIndex(null);
            }}
            className={`flex items-center gap-3 px-3 py-2 ${dragIndex === i ? "opacity-40" : ""} ${
              isTarget ? "bg-primary-50 ring-1 ring-inset ring-primary-300" : "bg-white"
            }`}
          >
            <span
              className={`select-none text-lg leading-none text-neutral-400 ${disabled ? "" : "cursor-grab active:cursor-grabbing"}`}
              title="Drag to reorder"
              aria-hidden
            >
              ⋮⋮
            </span>
            <span className="w-6 text-right text-xs tabular-nums text-neutral-400">{i + 1}</span>
            {item.image_url ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={item.image_url} alt="" className="h-9 w-9 rounded object-cover" />
            ) : (
              <span className="h-9 w-9 rounded bg-neutral-100" />
            )}
            <span className="min-w-0 flex-1 truncate text-sm font-medium text-primary-900">{item.name}</span>
            {item.status !== "ACTIVE" && (
              <span className="rounded-full bg-neutral-100 px-2 py-0.5 text-xs text-neutral-500">{item.status}</span>
            )}
            <span className="inline-flex shrink-0 gap-1">
              {buttons.map(([label, title, action, off]) => (
                <button
                  key={title}
                  type="button"
                  title={title}
                  aria-label={`${title}: ${item.name}`}
                  disabled={disabled || off}
                  onClick={action}
                  className="h-7 w-7 rounded border border-neutral-200 text-sm text-neutral-600 hover:bg-neutral-50 disabled:cursor-not-allowed disabled:opacity-30"
                >
                  {label}
                </button>
              ))}
            </span>
          </li>
        );
      })}
    </ul>
  );
}

export default function CategoryOrderPage() {
  const { getAccessToken, user } = useAuth();
  const canEdit = Boolean(user && hasPermission(user.roles, "categories.update"));

  // Working order: top-level list, and subcategories keyed by parent id.
  const [top, setTop] = useState<AdminCategoryListItem[]>([]);
  const [subs, setSubs] = useState<Record<number, AdminCategoryListItem[]>>({});
  const [dirty, setDirty] = useState<Set<number | "top">>(new Set());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);

  const load = useCallback(async () => {
    const token = getAccessToken();
    if (!token) return;
    setLoading(true);
    setError(null);
    try {
      const result = await fetchAdminCategories(token, { page: 1, page_size: 100 });
      const all = [...result.items].sort((a, b) => a.sort_order - b.sort_order || a.name.localeCompare(b.name));
      const grouped: Record<number, AdminCategoryListItem[]> = {};
      for (const c of all) {
        if (c.parent_id !== null) (grouped[c.parent_id] ??= []).push(c);
      }
      setTop(all.filter((c) => c.parent_id === null));
      setSubs(grouped);
      setDirty(new Set());
    } catch (err) {
      setError(err instanceof CategoryApiError ? err.message : "Unable to load categories.");
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const markDirty = (key: number | "top") => setDirty((d) => new Set(d).add(key));

  const save = async () => {
    const token = getAccessToken();
    if (!token) return;
    setSaving(true);
    setMessage(null);
    try {
      if (dirty.has("top")) await reorderCategories(token, top.map((c) => c.id));
      for (const key of dirty) {
        if (key !== "top") await reorderCategories(token, subs[key].map((c) => c.id));
      }
      setDirty(new Set());
      setMessage({ ok: true, text: "Order saved. The app shows it on its next refresh." });
    } catch (err) {
      setMessage({ ok: false, text: err instanceof CategoryApiError ? err.message : "Unable to save the order." });
    } finally {
      setSaving(false);
    }
  };

  const parentsWithSubs = top.filter((c) => (subs[c.id]?.length ?? 0) > 0);

  return (
    <div>
      <PageHeader
        eyebrow="Catalog"
        title="Display order"
        description="Choose which categories and subcategories customers see first. Drag rows by the handle, or use the arrow buttons. The first subcategories feed the bento grid on the app's home screen."
        actions={
          <>
            <Link
              href="/categories"
              className="rounded border border-neutral-300 px-4 py-2 text-sm font-semibold text-neutral-700 hover:bg-neutral-50"
            >
              Back
            </Link>
            {canEdit && (
              <button
                onClick={save}
                disabled={saving || dirty.size === 0}
                className="rounded bg-primary-800 px-4 py-2 text-sm font-semibold text-white hover:bg-primary-700 disabled:opacity-50"
              >
                {saving ? "Saving…" : dirty.size === 0 ? "Saved" : "Save order"}
              </button>
            )}
          </>
        }
      />

      {message && (
        <p
          className={`mb-4 rounded border px-3 py-2 text-sm ${
            message.ok
              ? "border-green-200 bg-green-50 text-green-800"
              : "border-status-danger/30 bg-status-dangerLight text-status-danger"
          }`}
        >
          {message.text}
        </p>
      )}

      {loading ? (
        <TableSkeleton rows={6} columns={3} />
      ) : error ? (
        <ErrorState message={error} onRetry={load} />
      ) : (
        <div className="grid gap-6 lg:grid-cols-2">
          <section className="overflow-hidden rounded border border-neutral-200 bg-white">
            <h2 className="border-b border-neutral-200 bg-neutral-50 px-4 py-2 text-xs font-medium uppercase tracking-wide text-neutral-500">
              Categories
            </h2>
            <OrderList
              items={top}
              disabled={!canEdit || saving}
              onChange={(next) => {
                setTop(next);
                markDirty("top");
              }}
            />
          </section>

          <div className="space-y-6">
            {parentsWithSubs.length === 0 && (
              <p className="rounded border border-dashed border-neutral-300 p-4 text-sm text-neutral-500">
                No subcategories yet.
              </p>
            )}
            {parentsWithSubs.map((parent) => (
              <section key={parent.id} className="overflow-hidden rounded border border-neutral-200 bg-white">
                <h2 className="border-b border-neutral-200 bg-neutral-50 px-4 py-2 text-xs font-medium uppercase tracking-wide text-neutral-500">
                  Subcategories of {parent.name}
                </h2>
                <OrderList
                  items={subs[parent.id]}
                  disabled={!canEdit || saving}
                  onChange={(next) => {
                    setSubs((s) => ({ ...s, [parent.id]: next }));
                    markDirty(parent.id);
                  }}
                />
              </section>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
