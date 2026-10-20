"use client";

import React from "react";
import type { Category } from "@/lib/products";

/** "Also show in" picker: ticks the extra categories/subcategories a product
 * is listed under besides its main one. */
export function CategoryChecklist({
  categories,
  mainCategoryId,
  selected,
  onChange,
  disabled,
}: {
  categories: Category[];
  mainCategoryId: string;
  selected: number[];
  onChange: (ids: number[]) => void;
  disabled?: boolean;
}) {
  const options = categories.filter((c) => String(c.id) !== mainCategoryId);
  if (options.length === 0) return <p className="text-sm text-neutral-400">No other categories.</p>;
  const toggle = (id: number) =>
    onChange(selected.includes(id) ? selected.filter((i) => i !== id) : [...selected, id]);
  return (
    <div className="max-h-44 space-y-1 overflow-y-auto rounded border border-neutral-300 p-2">
      {options.map((c) => (
        <label key={c.id} className={`flex items-center gap-2 text-sm text-neutral-700 ${c.parent_id ? "pl-5" : "font-bold"}`}>
          <input type="checkbox" disabled={disabled} checked={selected.includes(c.id)} onChange={() => toggle(c.id)} />
          {c.name}
        </label>
      ))}
    </div>
  );
}
