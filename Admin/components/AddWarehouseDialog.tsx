"use client";

import React, { useState } from "react";
import { useAuth } from "@/lib/auth-context";
import { createLocation, InventoryApiError } from "@/lib/inventory";

const EMPTY = { name: "", code: "", address_line_1: "", address_line_2: "", city: "", state: "", postal_code: "" };

export function AddWarehouseDialog({ open, onClose, onCreated }: { open: boolean; onClose: () => void; onCreated: () => void }) {
  const { getAccessToken } = useAuth();

  const [form, setForm] = useState(EMPTY);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!open) return null;

  const set = (key: keyof typeof EMPTY) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [key]: e.target.value }));

  const complete = Boolean(
    form.name.trim() && form.code.trim() && form.address_line_1.trim() && form.city.trim() && form.state.trim() && form.postal_code.trim(),
  );

  const handleClose = () => {
    setForm(EMPTY);
    setError(null);
    onClose();
  };

  const handleSubmit = async () => {
    const token = getAccessToken();
    if (!token || !complete) return;
    setSaving(true);
    setError(null);
    try {
      await createLocation(token, {
        name: form.name.trim(),
        code: form.code.trim().toUpperCase(),
        type: "WAREHOUSE",
        address_line_1: form.address_line_1.trim(),
        address_line_2: form.address_line_2.trim() || null,
        city: form.city.trim(),
        state: form.state.trim(),
        postal_code: form.postal_code.trim(),
      });
      handleClose();
      onCreated();
    } catch (err) {
      setError(err instanceof InventoryApiError ? err.message : "Unable to add this warehouse.");
    } finally {
      setSaving(false);
    }
  };

  const input = "w-full rounded border border-neutral-300 px-3 py-2 text-sm";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4">
      <div className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded bg-white p-6 shadow-xl">
        <h2 className="mb-4 font-display text-lg font-semibold text-primary-900">Add warehouse</h2>

        <Field label="Name">
          <input value={form.name} onChange={set("name")} placeholder="e.g. Nagpur Main Hub" className={input} />
        </Field>
        <Field label="Code">
          <input value={form.code} onChange={set("code")} placeholder="Short unique code, e.g. NGP1" className={`${input} uppercase`} />
        </Field>
        <Field label="Address line 1">
          <input value={form.address_line_1} onChange={set("address_line_1")} className={input} />
        </Field>
        <Field label="Address line 2 (optional)">
          <input value={form.address_line_2} onChange={set("address_line_2")} className={input} />
        </Field>
        <div className="grid grid-cols-1 gap-x-3 sm:grid-cols-3">
          <Field label="City">
            <input value={form.city} onChange={set("city")} className={input} />
          </Field>
          <Field label="State">
            <input value={form.state} onChange={set("state")} className={input} />
          </Field>
          <Field label="PIN code">
            <input value={form.postal_code} onChange={set("postal_code")} inputMode="numeric" className={input} />
          </Field>
        </div>

        {error && <p className="mb-3 rounded border border-status-danger/30 bg-status-dangerLight px-3 py-2 text-sm text-status-danger">{error}</p>}

        <div className="mt-4 flex justify-end gap-2">
          <button onClick={handleClose} className="rounded border border-neutral-300 px-4 py-2 text-sm font-medium text-neutral-700">Cancel</button>
          <button
            onClick={handleSubmit}
            disabled={saving || !complete}
            className="rounded bg-primary-800 px-4 py-2 text-sm font-semibold text-white disabled:opacity-40"
          >
            {saving ? "Adding..." : "Add warehouse"}
          </button>
        </div>
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="mb-3">
      <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-neutral-500">{label}</label>
      {children}
    </div>
  );
}
