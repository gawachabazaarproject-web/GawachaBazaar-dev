"use client";

import React, { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/lib/auth-context";
import {
  assignStaffRole,
  createStaff,
  fetchStaff,
  revokeStaffRole,
  setStaffStatus,
  StaffApiError,
  StaffListItem,
  STAFF_ROLES,
} from "@/lib/staff";
import { formatDate } from "@/lib/format";
import { PageHeader } from "@/components/PageHeader";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { TableSkeleton } from "@/components/TableSkeleton";
import { StatusBadge } from "@/components/StatusBadge";

const ROLE_LABELS: Record<string, string> = {
  ADMIN: "Admin",
  HUB_STAFF: "Hub Staff",
  OPERATIONS: "Operations",
  DELIVERY_PARTNER: "Delivery Partner",
  SUPPORT: "Support",
};

export default function StaffPage() {
  const { getAccessToken } = useAuth();
  const [staff, setStaff] = useState<StaffListItem[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [addOpen, setAddOpen] = useState(false);
  const [rowBusy, setRowBusy] = useState<number | null>(null);
  const [addRoleFor, setAddRoleFor] = useState<number | null>(null);

  const load = useCallback(async () => {
    const token = getAccessToken();
    if (!token) return;
    setLoading(true);
    setError(null);
    try {
      setStaff(await fetchStaff(token));
    } catch (err) {
      setError(err instanceof StaffApiError ? err.message : "Unable to load staff.");
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const withRowBusy = async (id: number, action: () => Promise<void>) => {
    setRowBusy(id);
    try {
      await action();
      await load();
    } catch (err) {
      setError(err instanceof StaffApiError ? err.message : "Something went wrong.");
    } finally {
      setRowBusy(null);
    }
  };

  const handleAssignRole = (id: number, role: string) => {
    setAddRoleFor(null);
    void withRowBusy(id, async () => {
      const token = getAccessToken();
      if (!token) return;
      await assignStaffRole(token, id, role);
    });
  };

  const handleRevokeRole = (id: number, role: string) => {
    void withRowBusy(id, async () => {
      const token = getAccessToken();
      if (!token) return;
      await revokeStaffRole(token, id, role);
    });
  };

  const handleToggleStatus = (member: StaffListItem) => {
    const next = member.status === "ACTIVE" ? "SUSPENDED" : "ACTIVE";
    void withRowBusy(member.id, async () => {
      const token = getAccessToken();
      if (!token) return;
      await setStaffStatus(token, member.id, next);
    });
  };

  return (
    <div>
      <PageHeader
        eyebrow="Operations"
        title="Staff"
        description="Internal accounts and the operational roles that gate the rest of this admin panel."
        actions={
          <button
            onClick={() => setAddOpen(true)}
            className="rounded bg-primary-800 px-4 py-2 text-sm font-semibold text-white hover:bg-primary-700"
          >
            + Add staff
          </button>
        }
      />

      {error && (
        <p className="mb-4 rounded border border-status-danger/30 bg-status-dangerLight px-3 py-2 text-sm text-status-danger">
          {error}
        </p>
      )}

      <div className="overflow-hidden rounded border border-neutral-200 bg-white">
        {loading ? (
          <TableSkeleton rows={6} columns={5} />
        ) : !staff || staff.length === 0 ? (
          <EmptyState
            icon="users"
            title="No staff accounts yet"
            message="Add your first team member and assign them a role."
            action={
              <button
                onClick={() => setAddOpen(true)}
                className="rounded bg-primary-800 px-4 py-2 text-sm font-semibold text-white hover:bg-primary-700"
              >
                + Add staff
              </button>
            }
          />
        ) : error && !staff.length ? (
          <ErrorState message={error} onRetry={load} />
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-neutral-200 bg-neutral-50 text-left text-xs font-semibold uppercase tracking-wide text-neutral-500">
                <th className="px-4 py-3">Name</th>
                <th className="px-4 py-3">Contact</th>
                <th className="px-4 py-3">Roles</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Joined</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-100">
              {staff.map((member) => {
                const busy = rowBusy === member.id;
                const availableToAdd = STAFF_ROLES.filter((r) => !member.roles.includes(r));
                return (
                  <tr key={member.id} className={busy ? "opacity-50" : undefined}>
                    <td className="px-4 py-3 font-medium text-primary-900">{member.name}</td>
                    <td className="px-4 py-3 text-neutral-600">
                      <div>{member.email}</div>
                      <div className="text-xs text-neutral-400">{member.phone}</div>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex flex-wrap items-center gap-1.5">
                        {member.roles.map((role) => (
                          <span
                            key={role}
                            className="inline-flex items-center gap-1 rounded bg-primary-50 px-2 py-0.5 text-xs font-semibold text-primary-800"
                          >
                            {ROLE_LABELS[role] ?? role}
                            <button
                              disabled={busy}
                              onClick={() => handleRevokeRole(member.id, role)}
                              aria-label={`Remove ${role}`}
                              className="text-primary-400 hover:text-status-danger"
                            >
                              ×
                            </button>
                          </span>
                        ))}
                        {availableToAdd.length > 0 &&
                          (addRoleFor === member.id ? (
                            <select
                              autoFocus
                              disabled={busy}
                              defaultValue=""
                              onBlur={() => setAddRoleFor(null)}
                              onChange={(e) => e.target.value && handleAssignRole(member.id, e.target.value)}
                              className="rounded border border-neutral-300 bg-white px-1.5 py-0.5 text-xs"
                            >
                              <option value="" disabled>
                                Choose role
                              </option>
                              {availableToAdd.map((r) => (
                                <option key={r} value={r}>
                                  {ROLE_LABELS[r] ?? r}
                                </option>
                              ))}
                            </select>
                          ) : (
                            <button
                              disabled={busy}
                              onClick={() => setAddRoleFor(member.id)}
                              className="rounded border border-dashed border-neutral-300 px-2 py-0.5 text-xs font-semibold text-neutral-500 hover:border-primary-400 hover:text-primary-700"
                            >
                              + role
                            </button>
                          ))}
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status={member.status} />
                    </td>
                    <td className="px-4 py-3 text-neutral-500">{formatDate(member.created_at)}</td>
                    <td className="px-4 py-3 text-right">
                      <button
                        disabled={busy}
                        onClick={() => handleToggleStatus(member)}
                        className="text-xs font-semibold text-neutral-500 hover:text-primary-700 hover:underline disabled:opacity-40"
                      >
                        {member.status === "ACTIVE" ? "Suspend" : "Reactivate"}
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      {addOpen && (
        <AddStaffDialog
          onClose={() => setAddOpen(false)}
          onCreated={() => {
            setAddOpen(false);
            load();
          }}
        />
      )}
    </div>
  );
}

function AddStaffDialog({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const { getAccessToken } = useAuth();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<string>(STAFF_ROLES[1]); // default to HUB_STAFF, not ADMIN
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async () => {
    const token = getAccessToken();
    if (!token || !name || !email || !phone || !password) return;
    setSaving(true);
    setError(null);
    try {
      await createStaff(token, { name, email, phone, password, role });
      onCreated();
    } catch (err) {
      setError(err instanceof StaffApiError ? err.message : "Unable to create staff account.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4">
      <div className="w-full max-w-md rounded bg-white p-6 shadow-xl">
        <h2 className="mb-4 font-display text-lg font-semibold text-primary-900">Add staff account</h2>

        <Field label="Full name">
          <input value={name} onChange={(e) => setName(e.target.value)} className="w-full rounded border border-neutral-300 px-3 py-2 text-sm" />
        </Field>
        <Field label="Email">
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full rounded border border-neutral-300 px-3 py-2 text-sm"
          />
        </Field>
        <Field label="Phone">
          <input value={phone} onChange={(e) => setPhone(e.target.value)} className="w-full rounded border border-neutral-300 px-3 py-2 text-sm" />
        </Field>
        <Field label="Temporary password">
          <input
            type="text"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="At least 8 characters"
            className="w-full rounded border border-neutral-300 px-3 py-2 text-sm"
          />
        </Field>
        <Field label="Role">
          <select
            value={role}
            onChange={(e) => setRole(e.target.value)}
            className="w-full rounded border border-neutral-300 bg-white px-3 py-2 text-sm"
          >
            {STAFF_ROLES.map((r) => (
              <option key={r} value={r}>
                {ROLE_LABELS[r] ?? r}
              </option>
            ))}
          </select>
        </Field>

        {error && <p className="mb-3 rounded border border-status-danger/30 bg-status-dangerLight px-3 py-2 text-sm text-status-danger">{error}</p>}

        <div className="mt-4 flex justify-end gap-2">
          <button onClick={onClose} className="rounded border border-neutral-300 px-4 py-2 text-sm font-medium text-neutral-700">
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={saving || !name || !email || !phone || password.length < 8}
            className="rounded bg-primary-800 px-4 py-2 text-sm font-semibold text-white disabled:opacity-40"
          >
            {saving ? "Creating..." : "Create account"}
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
