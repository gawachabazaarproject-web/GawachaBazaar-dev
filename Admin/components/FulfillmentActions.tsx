"use client";

import React, { useEffect, useState } from "react";
import { BusyLabel, Spinner } from "@/components/Spinner";
import { useAuth } from "@/lib/auth-context";
import { hasPermission } from "@/lib/permissions";
import { FulfillmentInfo } from "@/lib/orders";
import { fetchStaff, StaffListItem } from "@/lib/staff";
import {
  advanceFulfillment,
  assignDeliveryPartner,
  confirmDelivery,
  FulfillmentApiError,
  markOutForDelivery,
  WarehouseStep,
} from "@/lib/fulfillment";
import { SearchableSelect } from "@/components/SearchableSelect";

const WAREHOUSE_NEXT: Record<string, { status: WarehouseStep; label: string }> = {
  PENDING: { status: "PICKING", label: "Start picking" },
  PICKING: { status: "PACKED", label: "Mark packed" },
  PACKED: { status: "READY_FOR_DELIVERY", label: "Mark ready for delivery" },
};

const primary = "rounded bg-primary-800 px-4 py-2 text-sm font-semibold text-white hover:bg-primary-700 disabled:opacity-40";

/** The single next step for this order's delivery, for staff allowed to take it. */
export function FulfillmentActions({
  fulfillment,
  isCashOnDelivery,
  onChanged,
}: {
  fulfillment: FulfillmentInfo;
  isCashOnDelivery: boolean;
  onChanged: () => void;
}) {
  const { getAccessToken, user } = useAuth();
  const [partners, setPartners] = useState<StaffListItem[] | null>(null);
  const [partnerId, setPartnerId] = useState("");
  const [otp, setOtp] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const status = fulfillment.status;
  const canAssign = Boolean(user && hasPermission(user.roles, "delivery.assign"));
  const canFulfill = Boolean(user && hasPermission(user.roles, "delivery.fulfill"));
  const needsPartners = status === "READY_FOR_DELIVERY" && canAssign;

  useEffect(() => {
    if (!needsPartners) return;
    const token = getAccessToken();
    if (!token) return;
    fetchStaff(token)
      .then((staff) => setPartners(staff.filter((s) => s.status === "ACTIVE" && s.roles.includes("DELIVERY_PARTNER"))))
      .catch(() => setPartners([]));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [needsPartners]);

  const run = async (action: (token: string) => Promise<void>) => {
    const token = getAccessToken();
    if (!token) return;
    setBusy(true);
    setError(null);
    try {
      await action(token);
      onChanged();
    } catch (err) {
      // A 409 ("Cannot ... from status X") means this page was out of date
      // (another tab/admin already moved the delivery) - resync so the
      // screen shows the real status instead of a stale one.
      if (err instanceof FulfillmentApiError && err.message.includes("from status")) {
        setError("This delivery was already updated by someone else - the page has been refreshed.");
        onChanged();
      } else {
        setError(err instanceof FulfillmentApiError ? err.message : "Unable to update this delivery.");
      }
    } finally {
      setBusy(false);
    }
  };

  let content: React.ReactNode = null;
  const next = WAREHOUSE_NEXT[status];

  if (next && canAssign) {
    content = (
      <button disabled={busy} onClick={() => run((t) => advanceFulfillment(t, fulfillment.id, next.status))} className={primary}>
        {busy ? <BusyLabel>Updating...</BusyLabel> : next.label}
      </button>
    );
  } else if (needsPartners) {
    content =
      partners === null ? (
        <p className="inline-flex items-center gap-2 text-sm text-neutral-500"><Spinner />Loading delivery partners...</p>
      ) : partners.length === 0 ? (
        <p className="text-sm text-neutral-600">
          No active staff member has the Delivery Partner role. Add one under Staff (or give yourself that role), then come back here.
        </p>
      ) : (
        <div className="flex flex-wrap items-center gap-2">
          <SearchableSelect
            className="w-64"
            value={partnerId}
            onChange={setPartnerId}
            placeholder="Choose a delivery partner"
            options={partners.map((p) => ({ value: String(p.id), label: p.name }))}
          />
          <button
            disabled={busy || !partnerId}
            onClick={() => run((t) => assignDeliveryPartner(t, fulfillment.id, Number(partnerId)))}
            className={primary}
          >
            {busy ? <BusyLabel>Assigning...</BusyLabel> : "Assign"}
          </button>
        </div>
      );
  } else if (status === "ASSIGNED" && canFulfill) {
    content = (
      <button disabled={busy} onClick={() => run((t) => markOutForDelivery(t, fulfillment.id))} className={primary}>
        {busy ? <BusyLabel>Updating...</BusyLabel> : "Mark out for delivery"}
      </button>
    );
  } else if (status === "OUT_FOR_DELIVERY" && canFulfill) {
    content = (
      <div>
        <label className="block text-sm font-medium text-neutral-700" htmlFor="delivery-otp">
          Delivery code from the customer
        </label>
        <p className="mb-2 text-xs text-neutral-500">
          The customer sees a 6-digit code in their app. Ask them to read it out - the order cannot be completed without it.
        </p>
        <div className="flex flex-wrap items-center gap-2">
          <input
            id="delivery-otp"
            value={otp}
            onChange={(e) => setOtp(e.target.value.replace(/\D/g, "").slice(0, 6))}
            inputMode="numeric"
            maxLength={6}
            autoComplete="off"
            placeholder="6-digit code"
            className="w-36 rounded border border-neutral-300 px-3 py-2 text-center text-lg tracking-widest"
          />
          <button
            disabled={busy || otp.length !== 6}
            onClick={() => run(async (t) => { await confirmDelivery(t, fulfillment.id, otp); setOtp(""); })}
            className={primary}
          >
            {busy ? <BusyLabel>Confirming...</BusyLabel> : isCashOnDelivery ? "Confirm delivered - cash collected" : "Confirm delivered"}
          </button>
        </div>
        <p className="mt-2 text-xs text-neutral-500">
          This can&apos;t be undone. It deducts the stock
          {isCashOnDelivery ? " and records the Cash on Delivery payment as paid." : "."}
        </p>
      </div>
    );
  }

  if (!content) return null;

  return (
    <div className="mt-3 border-t border-neutral-200 pt-3">
      {content}
      {error && <p className="mt-2 rounded border border-status-danger/30 bg-status-dangerLight px-3 py-2 text-sm text-status-danger">{error}</p>}
    </div>
  );
}
