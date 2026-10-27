"use client";

import React, { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/lib/auth-context";
import { hasPermission } from "@/lib/permissions";
import { PageHeader } from "@/components/PageHeader";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { StatusBadge } from "@/components/StatusBadge";
import {
  ActiveDelivery,
  CodList,
  EarningsSummary,
  PartnerAssignment,
  PartnerProfile,
  PartnersApiError,
  partnersApi,
} from "@/lib/partners";

type Tab = "partners" | "assignments" | "active" | "cod" | "earnings";
const TABS: { id: Tab; label: string }[] = [
  { id: "partners", label: "Partners" },
  { id: "assignments", label: "Assignments" },
  { id: "active", label: "Active now" },
  { id: "cod", label: "COD cash" },
  { id: "earnings", label: "Earnings" },
];

/** Delivery-partner operations. Every action is re-authorised by the backend
 * (partners.read / partners.manage / partners.cod_reconcile); hiding a button
 * here is convenience only. */
export default function DeliveryPartnersPage() {
  const { getAccessToken, user } = useAuth();
  const canManage = !!user && hasPermission(user.roles, "partners.manage");
  const canReconcile = !!user && hasPermission(user.roles, "partners.cod_reconcile");
  const [tab, setTab] = useState<Tab>("partners");
  const [partners, setPartners] = useState<PartnerProfile[]>([]);
  const [assignments, setAssignments] = useState<PartnerAssignment[]>([]);
  const [active, setActive] = useState<ActiveDelivery[]>([]);
  const [cod, setCod] = useState<CodList | null>(null);
  const [earnings, setEarnings] = useState<EarningsSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    const token = getAccessToken();
    if (!token) return;
    setLoading(true);
    setError(null);
    try {
      if (tab === "partners") setPartners((await partnersApi.partners(token)).items);
      if (tab === "assignments") setAssignments((await partnersApi.assignments(token)).items);
      if (tab === "active") setActive(await partnersApi.active(token));
      if (tab === "cod") setCod(await partnersApi.cod(token));
      if (tab === "earnings") setEarnings(await partnersApi.earnings(token));
    } catch (e) {
      setError(e instanceof PartnersApiError ? e.message : "Unable to load.");
    } finally {
      setLoading(false);
    }
  }, [tab, getAccessToken]);

  useEffect(() => {
    load();
  }, [load]);

  const act = async (fn: (token: string) => Promise<unknown>) => {
    const token = getAccessToken();
    if (!token) return;
    try {
      await fn(token);
      await load();
    } catch (e) {
      setError(e instanceof PartnersApiError ? e.message : "Action failed.");
    }
  };

  return (
    <div>
      <PageHeader
        eyebrow="Sell"
        title="Delivery partners"
        description="Partners, assignments, live deliveries, cash on delivery and earnings."
      />
      <div className="mb-4 flex gap-2">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`rounded px-3 py-1.5 text-sm font-semibold ${
              tab === t.id ? "bg-primary-900 text-white" : "bg-neutral-200 text-neutral-700"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>
      {error && <ErrorState message={error} onRetry={load} />}
      {loading && <p className="text-sm text-neutral-500">Loading...</p>}

      {!loading && !error && tab === "partners" &&
        (partners.length === 0 ? (
          <EmptyState title="No partners yet" message="Give a user the DELIVERY_PARTNER role first." />
        ) : (
          <table className="w-full text-sm">
            <thead><tr className="text-left"><th>Name</th><th>Status</th><th>Availability</th><th>Vehicle</th><th /></tr></thead>
            <tbody>
              {partners.map((p) => (
                <tr key={p.user_id} className="border-t">
                  <td>{p.name ?? `#${p.user_id}`}</td>
                  <td><StatusBadge status={p.status} /></td>
                  <td>{p.availability}</td>
                  <td>{p.vehicle_type} {p.vehicle_number ?? ""}</td>
                  <td>
                    {canManage &&
                      (p.status === "ACTIVE" ? (
                        <button className="text-status-danger" onClick={() => act((t) => partnersApi.setStatus(t, p.user_id, "SUSPENDED"))}>Suspend</button>
                      ) : (
                        <button className="text-primary-700" onClick={() => act((t) => partnersApi.setStatus(t, p.user_id, "ACTIVE"))}>Activate</button>
                      ))}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ))}

      {!loading && !error && tab === "assignments" &&
        (assignments.length === 0 ? (
          <EmptyState title="No assignments" message="Assign a delivery from the Delivery queue." />
        ) : (
          <table className="w-full text-sm">
            <thead><tr className="text-left"><th>Order</th><th>Partner</th><th>Status</th><th>COD</th><th>Assigned</th></tr></thead>
            <tbody>
              {assignments.map((a) => (
                <tr key={a.id} className="border-t">
                  <td>#{a.order_number}</td>
                  <td>{a.partner_user_id}</td>
                  <td><StatusBadge status={a.status} /></td>
                  <td>{a.cod_status} {a.cod_expected_amount}</td>
                  <td>{new Date(a.assigned_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ))}

      {!loading && !error && tab === "active" &&
        (active.length === 0 ? (
          <EmptyState title="Nothing on the road" message="Active deliveries appear here with their last known position." />
        ) : (
          <table className="w-full text-sm">
            <thead><tr className="text-left"><th>Order</th><th>Partner</th><th>Status</th><th>Last position</th></tr></thead>
            <tbody>
              {active.map((a) => (
                <tr key={a.assignment_id} className="border-t">
                  <td>{a.order_id}</td>
                  <td>{a.partner_user_id}</td>
                  <td><StatusBadge status={a.status} /></td>
                  <td>
                    {a.latitude != null && a.longitude != null ? (
                      <a className="text-primary-700 underline" target="_blank" rel="noreferrer" href={`https://www.google.com/maps?q=${a.latitude},${a.longitude}`}>
                        {a.latitude.toFixed(4)}, {a.longitude.toFixed(4)}
                      </a>
                    ) : (
                      "-"
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ))}

      {!loading && !error && tab === "cod" && cod && (
        <div>
          <p className="mb-3 text-sm">Collected and not yet handed over: <strong>Rs {cod.outstanding_amount}</strong></p>
          {cod.items.length === 0 ? (
            <EmptyState title="No COD records" message="Cash collected by partners will be listed here." />
          ) : (
            <table className="w-full text-sm">
              <thead><tr className="text-left"><th>Order</th><th>Partner</th><th>Status</th><th>Expected</th><th>Collected</th><th /></tr></thead>
              <tbody>
                {cod.items.map((c) => (
                  <tr key={c.assignment_id} className="border-t">
                    <td>{c.order_id}</td>
                    <td>{c.partner_user_id}</td>
                    <td><StatusBadge status={c.cod_status} /></td>
                    <td>{c.cod_expected_amount}</td>
                    <td>{c.cod_collected_amount ?? "-"}</td>
                    <td>
                      {c.cod_reconciled_at ? (
                        "Reconciled"
                      ) : c.cod_status === "COD_COLLECTED" && canReconcile ? (
                        <button className="text-primary-700" onClick={() => act((t) => partnersApi.reconcile(t, c.assignment_id))}>Mark handed over</button>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {!loading && !error && tab === "earnings" &&
        (earnings.length === 0 ? (
          <EmptyState title="No earnings yet" message="Earnings are recorded when a delivery completes." />
        ) : (
          <table className="w-full text-sm">
            <thead><tr className="text-left"><th>Partner</th><th>Deliveries</th><th>Total (Rs)</th></tr></thead>
            <tbody>
              {earnings.map((e) => (
                <tr key={e.partner_user_id} className="border-t"><td>{e.partner_user_id}</td><td>{e.deliveries}</td><td>{e.total}</td></tr>
              ))}
            </tbody>
          </table>
        ))}
    </div>
  );
}
