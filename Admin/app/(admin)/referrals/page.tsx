"use client";

import React, { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/lib/auth-context";
import { hasPermission } from "@/lib/permissions";
import { PageHeader } from "@/components/PageHeader";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { StatusBadge } from "@/components/StatusBadge";
import { AdminReferral, PartnersApiError, partnersApi } from "@/lib/partners";

const STATUSES = ["", "PENDING", "QUALIFIED", "REWARDED", "REVERSED", "CANCELLED"];

/** Refer & Earn administration: review referrals and reverse a reward. */
export default function ReferralsPage() {
  const { getAccessToken, user } = useAuth();
  const canManage = !!user && hasPermission(user.roles, "referrals.manage");
  const [status, setStatus] = useState("");
  const [rows, setRows] = useState<AdminReferral[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    const token = getAccessToken();
    if (!token) return;
    setLoading(true);
    setError(null);
    try {
      setRows((await partnersApi.referrals(token, status || undefined)).items);
    } catch (e) {
      setError(e instanceof PartnersApiError ? e.message : "Unable to load referrals.");
    } finally {
      setLoading(false);
    }
  }, [status, getAccessToken]);

  useEffect(() => {
    load();
  }, [load]);

  const reverse = async (id: number) => {
    const reason = window.prompt("Reason for reversing this referral (required):");
    const token = getAccessToken();
    if (!reason || reason.trim().length < 3 || !token) return;
    try {
      await partnersApi.reverseReferral(token, id, reason.trim());
      await load();
    } catch (e) {
      setError(e instanceof PartnersApiError ? e.message : "Could not reverse.");
    }
  };

  return (
    <div>
      <PageHeader
        eyebrow="Marketing"
        title="Referrals"
        description="Who invited whom, and the rewards paid. Reversals are recorded in the ledger, never edited."
      />
      <select value={status} onChange={(e) => setStatus(e.target.value)} className="mb-4 rounded border px-2 py-1 text-sm">
        {STATUSES.map((s) => (
          <option key={s} value={s}>{s || "All statuses"}</option>
        ))}
      </select>
      {error && <ErrorState message={error} onRetry={load} />}
      {loading && <p className="text-sm text-neutral-500">Loading...</p>}
      {!loading && !error &&
        (rows.length === 0 ? (
          <EmptyState title="No referrals" message="Nothing matches this filter." />
        ) : (
          <table className="w-full text-sm">
            <thead><tr className="text-left"><th>#</th><th>Referrer</th><th>Referred</th><th>Status</th><th>Order</th><th>Applied</th><th /></tr></thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id} className="border-t">
                  <td>{r.id}</td>
                  <td>{r.referrer_user_id}</td>
                  <td>{r.referred_user_id}</td>
                  <td><StatusBadge status={r.status} /></td>
                  <td>{r.qualifying_order_id ?? "-"}</td>
                  <td>{new Date(r.applied_at).toLocaleDateString()}</td>
                  <td>
                    {canManage && !["REVERSED", "CANCELLED"].includes(r.status) && (
                      <button className="text-status-danger" onClick={() => reverse(r.id)}>Reverse</button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ))}
    </div>
  );
}
