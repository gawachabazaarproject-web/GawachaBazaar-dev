"use client";

import React, { useEffect, useId, useLayoutEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";

export interface SelectOption {
  value: string;
  label: string;
  /** Bold, used for top-level entries of a grouped list (e.g. main categories). */
  strong?: boolean;
  /** Indented, used for children (e.g. subcategories). */
  indent?: boolean;
}

/**
 * A dropdown you can type into to filter. Drop-in for a native <select> whose
 * options come from data (products, warehouses, categories...). Colours follow
 * the Admin theme: neutral border, primary focus ring, primary tint for the
 * selected option. Keyboard: type to filter, arrows to move, Enter to pick,
 * Esc to close.
 */
export function SearchableSelect({
  value,
  onChange,
  options,
  placeholder = "Choose...",
  disabled,
  required,
  className = "",
  ariaLabel,
}: {
  value: string;
  onChange: (value: string) => void;
  options: SelectOption[];
  /** Label of the empty choice (value ""), e.g. "Category: All" or "Choose a product". */
  placeholder?: string;
  disabled?: boolean;
  required?: boolean;
  className?: string;
  ariaLabel?: string;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const root = useRef<HTMLDivElement>(null);
  const popover = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLInputElement>(null);
  // The list floats above everything (portal + fixed position) so a dialog's
  // own scroll area or a table's overflow can never clip it.
  const [box, setBox] = useState<{ left: number; width: number; top?: number; bottom?: number; maxHeight: number } | null>(null);
  const listId = useId();

  const all = useMemo<SelectOption[]>(() => [{ value: "", label: placeholder }, ...options], [options, placeholder]);
  const shown = useMemo(() => {
    const q = query.trim().toLowerCase();
    return q ? all.filter((o) => o.value !== "" && o.label.toLowerCase().includes(q)) : all;
  }, [all, query]);
  const selected = options.find((o) => o.value === value);

  useLayoutEffect(() => {
    if (!open) return;
    const place = () => {
      const r = root.current?.getBoundingClientRect();
      if (!r) return;
      const below = window.innerHeight - r.bottom - 12;
      const above = r.top - 12;
      const flip = below < 220 && above > below; // little room underneath: open upwards
      const room = Math.max(160, Math.min(flip ? above : below, 340));
      setBox(
        flip
          ? { left: r.left, width: r.width, bottom: window.innerHeight - r.top + 4, maxHeight: room }
          : { left: r.left, width: r.width, top: r.bottom + 4, maxHeight: room },
      );
    };
    place();
    window.addEventListener("resize", place);
    window.addEventListener("scroll", place, true); // any scrolling ancestor, e.g. the dialog
    return () => {
      window.removeEventListener("resize", place);
      window.removeEventListener("scroll", place, true);
    };
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      const t = e.target as Node;
      if (root.current?.contains(t) || popover.current?.contains(t)) return;
      setOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [open]);

  useEffect(() => {
    if (open) {
      setQuery("");
      setActive(Math.max(0, all.findIndex((o) => o.value === value)));
      // Let the list render, then focus the search box.
      window.setTimeout(() => input.current?.focus(), 0);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  useEffect(() => setActive(0), [query]);

  const pick = (o: SelectOption) => {
    onChange(o.value);
    setOpen(false);
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((a) => Math.min(a + 1, shown.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((a) => Math.max(a - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (shown[active]) pick(shown[active]);
    } else if (e.key === "Escape") {
      e.preventDefault();
      setOpen(false);
    }
  };

  return (
    <div ref={root} className={`relative ${className}`}>
      <button
        type="button"
        disabled={disabled}
        aria-label={ariaLabel}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={listId}
        onClick={() => setOpen((o) => !o)}
        className={`flex w-full items-center justify-between gap-2 rounded border bg-white px-3 py-2 text-left text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 disabled:bg-neutral-50 disabled:text-neutral-400 ${
          open ? "border-primary-500 ring-1 ring-primary-500" : "border-neutral-300"
        }`}
      >
        <span className={`truncate ${selected ? "text-neutral-800" : "text-neutral-400"}`}>{selected ? selected.label : placeholder}</span>
        <svg className={`h-4 w-4 shrink-0 text-neutral-500 transition-transform ${open ? "rotate-180" : ""}`} viewBox="0 0 20 20" fill="currentColor" aria-hidden>
          <path fillRule="evenodd" d="M5.23 7.21a.75.75 0 011.06.02L10 11.17l3.71-3.94a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z" clipRule="evenodd" />
        </svg>
      </button>
      {/* Keeps native form validation working for required pickers. */}
      {required && <input tabIndex={-1} aria-hidden required value={value} onChange={() => undefined} className="pointer-events-none absolute inset-0 h-full w-full opacity-0" />}

      {open && box &&
        createPortal(
          <div
            ref={popover}
            style={{ position: "fixed", left: box.left, width: box.width, top: box.top, bottom: box.bottom, maxHeight: box.maxHeight }}
            className="z-[100] flex flex-col overflow-hidden rounded border border-neutral-200 bg-white text-[13px] shadow-xl"
          >
            <div className="shrink-0 border-b border-neutral-100 p-2">
              <input
                ref={input}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={onKeyDown}
                placeholder="Search..."
                aria-label="Search options"
                className="w-full rounded border border-neutral-300 px-2.5 py-1.5 text-[13px] focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
              />
            </div>
            <ul id={listId} role="listbox" className="min-h-0 flex-1 overflow-y-auto py-1">
              {shown.length === 0 ? (
                <li className="px-3 py-2 text-neutral-400">No matches</li>
              ) : (
                shown.map((o, i) => (
                  <li
                    key={o.value || "__empty"}
                    role="option"
                    aria-selected={o.value === value}
                    onMouseEnter={() => setActive(i)}
                    onMouseDown={(e) => {
                      e.preventDefault();
                      pick(o);
                    }}
                    className={`cursor-pointer px-3 py-1.5 ${o.indent ? "pl-6" : ""} ${o.strong ? "font-bold" : ""} ${
                      o.value === value ? "bg-primary-50 text-primary-900" : "text-neutral-700"
                    } ${i === active ? "bg-neutral-100" : ""} ${o.value === "" ? "text-neutral-400" : ""}`}
                  >
                    {o.label}
                  </li>
                ))
              )}
            </ul>
          </div>,
          document.body,
        )}
    </div>
  );
}

/** Options for a category list: main categories bold, subcategories indented. */
export function categoryOptions(categories: { id: number; name: string; parent_id: number | null }[]): SelectOption[] {
  return categories.map((c) => ({
    value: String(c.id),
    label: c.name,
    strong: c.parent_id === null,
    indent: c.parent_id !== null,
  }));
}
