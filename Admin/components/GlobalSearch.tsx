"use client";

import React, { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Icon, IconName } from "./icons";

export interface SearchPage {
  label: string;
  href: string;
  icon: IconName;
}

interface Result {
  key: string;
  label: string;
  hint: string;
  href: string;
  icon: IconName;
}

/**
 * Top-bar search. Press "/" or Ctrl/Cmd+K anywhere to focus it. Typing offers
 * (a) pages whose name matches and (b) "search <text> in <list>" shortcuts that
 * open the list page with `?q=` - the list pages read it on load. It never
 * calls the API itself, so it adds no load and shows no stale data.
 */
export function GlobalSearch({
  pages,
  searchable,
}: {
  pages: SearchPage[];
  /** List pages that understand `?q=` and that this user may open. */
  searchable: SearchPage[];
}) {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const boxRef = useRef<HTMLDivElement>(null);
  const [text, setText] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);

  const results = useMemo<Result[]>(() => {
    const term = text.trim();
    if (!term) return [];
    const lower = term.toLowerCase();
    const out: Result[] = searchable.map((p) => ({
      key: `q-${p.href}`,
      label: `Search ${p.label.toLowerCase()} for "${term}"`,
      hint: "Search",
      href: `${p.href}?q=${encodeURIComponent(term)}`,
      icon: p.icon,
    }));
    for (const p of pages) {
      if (p.label.toLowerCase().includes(lower)) {
        out.push({ key: `p-${p.href}`, label: `Go to ${p.label}`, hint: "Page", href: p.href, icon: p.icon });
      }
    }
    return out;
  }, [text, pages, searchable]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      const typing = !!target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.tagName === "SELECT" || target.isContentEditable);
      if ((e.key === "k" && (e.metaKey || e.ctrlKey)) || (e.key === "/" && !typing)) {
        e.preventDefault();
        inputRef.current?.focus();
        setOpen(true);
      }
    };
    const onClick = (e: MouseEvent) => {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    window.addEventListener("mousedown", onClick);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("mousedown", onClick);
    };
  }, []);

  const go = (r: Result) => {
    setOpen(false);
    setText("");
    inputRef.current?.blur();
    router.push(r.href);
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") {
      setOpen(false);
      inputRef.current?.blur();
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((i) => Math.min(i + 1, results.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter" && results[active]) {
      e.preventDefault();
      go(results[active]);
    }
  };

  return (
    <div ref={boxRef} className="relative min-w-0 max-w-md flex-1">
      <div className="flex items-center gap-2 rounded border border-neutral-200 bg-neutral-50 px-3 py-2 text-sm text-neutral-500 focus-within:border-primary-500 focus-within:ring-1 focus-within:ring-primary-500">
        <Icon name="search" size={16} />
        <input
          ref={inputRef}
          value={text}
          onChange={(e) => {
            setText(e.target.value);
            setActive(0);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={onKeyDown}
          role="combobox"
          aria-expanded={open && results.length > 0}
          aria-controls="global-search-results"
          aria-label="Search orders, products, customers and pages"
          placeholder="Search orders, products, customers..."
          className="min-w-0 flex-1 bg-transparent text-neutral-800 placeholder:text-neutral-500 focus:outline-none"
        />
        <kbd className="hidden rounded border border-neutral-300 px-1.5 text-[10px] font-semibold text-neutral-500 sm:block">/</kbd>
      </div>
      {open && results.length > 0 && (
        <ul
          id="global-search-results"
          role="listbox"
          className="absolute left-0 right-0 top-11 z-40 overflow-hidden rounded border border-neutral-200 bg-white shadow-xl"
        >
          {results.map((r, i) => (
            <li key={r.key} role="option" aria-selected={i === active}>
              <button
                type="button"
                onMouseEnter={() => setActive(i)}
                onClick={() => go(r)}
                className={`flex w-full items-center gap-3 px-3 py-2 text-left text-sm ${
                  i === active ? "bg-primary-50 text-primary-900" : "text-neutral-700"
                }`}
              >
                <Icon name={r.icon} size={15} />
                <span className="min-w-0 flex-1 truncate">{r.label}</span>
                <span className="text-xs text-neutral-400">{r.hint}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
