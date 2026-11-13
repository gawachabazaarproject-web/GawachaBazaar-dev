"use client";

import React from "react";

/**
 * Storefront look + visibility for one category. Shared by the Create and
 * Edit pages. Colours are restricted to presets that keep the dark tile
 * label readable (the backend re-checks contrast and rejects anything darker).
 */

export interface CategoryDisplay {
  background_color: string; // "" = app default
  badge_text: string;
  show_on_homepage: boolean;
  show_in_catalog: boolean;
  is_featured: boolean;
}

export const DEFAULT_DISPLAY: CategoryDisplay = {
  background_color: "",
  badge_text: "",
  show_on_homepage: true,
  show_in_catalog: true,
  is_featured: false,
};

export const COLOR_PRESETS: { name: string; hex: string }[] = [
  { name: "Sage", hex: "#E4EEDC" },
  { name: "Mint", hex: "#DDF0E4" },
  { name: "Warm Cream", hex: "#F6F0E0" },
  { name: "Soft Yellow", hex: "#FFF2CC" },
  { name: "Pale Peach", hex: "#FDE5D9" },
  { name: "Muted Lavender", hex: "#E8E3F3" },
  { name: "Light Green", hex: "#E2F2D3" },
];

const APP_DEFAULT_TILE = "#EFF4E6";

export function CategoryTilePreview({
  name,
  imageUrl,
  display,
  className = "",
}: {
  name: string;
  imageUrl?: string | null;
  display: CategoryDisplay;
  className?: string;
}) {
  const bg = display.background_color || APP_DEFAULT_TILE;
  return (
    <div className={`flex w-24 flex-col items-center gap-1.5 ${className}`}>
      <div
        className="relative flex h-24 w-24 items-center justify-center overflow-hidden rounded-2xl"
        style={{ backgroundColor: bg }}
      >
        {imageUrl ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={imageUrl} alt="" className="h-[80%] w-[80%] object-contain" />
        ) : (
          <span className="text-xs text-neutral-400">No image</span>
        )}
        {display.badge_text && (
          <span className="absolute left-1 top-1 rounded-full bg-secondary-500 px-1.5 py-0.5 text-[10px] font-bold uppercase leading-none text-primary-900">
            {display.badge_text}
          </span>
        )}
      </div>
      <span className="line-clamp-2 text-center text-xs font-medium text-primary-900">{name || "Category name"}</span>
    </div>
  );
}

function Toggle({
  label,
  hint,
  checked,
  disabled,
  onChange,
}: {
  label: string;
  hint: string;
  checked: boolean;
  disabled?: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <label className="flex cursor-pointer items-start gap-3 py-2">
      <input
        type="checkbox"
        checked={checked}
        disabled={disabled}
        onChange={(e) => onChange(e.target.checked)}
        className="mt-0.5 h-4 w-4 rounded border-neutral-300"
      />
      <span>
        <span className="block text-sm font-medium text-neutral-800">{label}</span>
        <span className="block text-xs text-neutral-500">{hint}</span>
      </span>
    </label>
  );
}

export function CategoryDisplayFields({
  value,
  onChange,
  name,
  imageUrl,
  disabled,
}: {
  value: CategoryDisplay;
  onChange: (next: CategoryDisplay) => void;
  name: string;
  imageUrl?: string | null;
  disabled?: boolean;
}) {
  const set = <K extends keyof CategoryDisplay>(key: K, v: CategoryDisplay[K]) => onChange({ ...value, [key]: v });

  return (
    <div className="grid gap-6 md:grid-cols-[1fr_auto]">
      <div>
        <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-neutral-500">Tile background</p>
        <div className="mb-4 flex flex-wrap gap-2">
          <button
            type="button"
            disabled={disabled}
            onClick={() => set("background_color", "")}
            aria-pressed={value.background_color === ""}
            className={`rounded-full border px-3 py-1 text-xs ${
              value.background_color === "" ? "border-primary-700 bg-primary-50 font-semibold" : "border-neutral-300"
            }`}
          >
            Default
          </button>
          {COLOR_PRESETS.map((c) => (
            <button
              key={c.hex}
              type="button"
              disabled={disabled}
              title={c.name}
              aria-label={c.name}
              aria-pressed={value.background_color === c.hex}
              onClick={() => set("background_color", c.hex)}
              className={`h-8 w-8 rounded-full border-2 ${
                value.background_color === c.hex ? "border-primary-700" : "border-neutral-200"
              }`}
              style={{ backgroundColor: c.hex }}
            />
          ))}
        </div>

        <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-neutral-500">Badge</label>
        <input
          value={value.badge_text}
          maxLength={24}
          disabled={disabled}
          onChange={(e) => set("badge_text", e.target.value)}
          placeholder="e.g. New, Fresh, 20% off"
          className="mb-1 w-full max-w-xs rounded border border-neutral-300 px-3 py-2 text-sm disabled:bg-neutral-50"
        />
        <p className="mb-4 text-xs text-neutral-400">Small label on the tile. Leave empty for none.</p>

        <div className="divide-y divide-neutral-100 rounded border border-neutral-200 px-3">
          <Toggle
            label="Show on Home"
            hint="Appears in the Shop by category grid on the app's home screen."
            checked={value.show_on_homepage}
            disabled={disabled}
            onChange={(v) => set("show_on_homepage", v)}
          />
          <Toggle
            label="Show in View all"
            hint="Appears in the full category list. Turn off to hide it from browsing."
            checked={value.show_in_catalog}
            disabled={disabled}
            onChange={(v) => set("show_in_catalog", v)}
          />
          <Toggle
            label="Featured"
            hint="Marks the category as a highlighted one."
            checked={value.is_featured}
            disabled={disabled}
            onChange={(v) => set("is_featured", v)}
          />
        </div>
        <p className="mt-2 text-xs text-neutral-400">
          Only <strong>Active</strong> categories are shown to customers, whatever these switches say.
        </p>
      </div>

      <div>
        <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-neutral-500">Preview</p>
        <div className="rounded border border-neutral-200 bg-[#F7F4EB] p-4">
          <CategoryTilePreview name={name} imageUrl={imageUrl} display={value} />
        </div>
        <p className="mt-2 max-w-[10rem] text-xs text-neutral-400">As it looks in the app (transparent PNG illustrations work best).</p>
      </div>
    </div>
  );
}
