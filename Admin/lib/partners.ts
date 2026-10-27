import { apiFetch } from "@/lib/api";

/** Types mirror backend/app/schemas/delivery_partner.py and referral.py. */
export interface PartnerProfile {
  user_id: number;
  name: string | null;
  status: string;
  availability: string;
  vehicle_type: string;
  vehicle_number: string | null;
  phone: string | null;
}
export interface PartnerAssignment {
  id: number;
  order_id: number;
  order_number: string;
  partner_user_id: number;
  status: string;
  cod_status: string;
  cod_expected_amount: string;
  cod_collected_amount: string | null;
  assigned_at: string;
  delivered_at: string | null;
}
export interface CodList {
  items: {
    assignment_id: number;
    order_id: number;
    partner_user_id: number;
    cod_status: string;
    cod_expected_amount: string;
    cod_collected_amount: string | null;
    cod_collected_at: string | null;
    cod_reconciled_at: string | null;
  }[];
  total: number;
  outstanding_amount: string;
}
export interface ActiveDelivery {
  assignment_id: number;
  order_id: number;
  partner_user_id: number;
  status: string;
  latitude: number | null;
  longitude: number | null;
  location_updated_at: string | null;
}
export interface EarningsSummary {
  partner_user_id: number;
  total: string;
  deliveries: number;
}
export interface AdminReferral {
  id: number;
  referrer_user_id: number;
  referred_user_id: number;
  status: string;
  qualifying_order_id: number | null;
  applied_at: string;
  rewarded_at: string | null;
  status_reason: string | null;
}

export class PartnersApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(token: string, path: string, init: RequestInit = {}): Promise<T> {
  const res = await apiFetch(path, token, init);
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new PartnersApiError(res.status, body?.message ?? "Request failed.");
  }
  return (await res.json()) as T;
}

export const partnersApi = {
  partners: (t: string) => request<{ items: PartnerProfile[]; total: number }>(t, "/delivery-partners?page_size=50"),
  setStatus: (t: string, userId: number, status: string) =>
    request<PartnerProfile>(t, `/delivery-partners/${userId}`, { method: "PATCH", body: JSON.stringify({ status }) }),
  assignments: (t: string, status?: string) =>
    request<{ items: PartnerAssignment[]; total: number }>(
      t,
      `/delivery-partners/assignments?page_size=50${status ? `&status=${status}` : ""}`,
    ),
  active: (t: string) => request<ActiveDelivery[]>(t, "/delivery-partners/active"),
  cod: (t: string, reconciled?: boolean) =>
    request<CodList>(t, `/delivery-partners/cod?page_size=50${reconciled === undefined ? "" : `&reconciled=${reconciled}`}`),
  reconcile: (t: string, assignmentId: number) =>
    request<unknown>(t, `/delivery-partners/assignments/${assignmentId}/cod-reconcile`, {
      method: "POST",
      body: JSON.stringify({}),
    }),
  earnings: (t: string) => request<EarningsSummary[]>(t, "/delivery-partners/earnings"),
  referrals: (t: string, status?: string) =>
    request<{ items: AdminReferral[]; total: number }>(t, `/referrals/admin?page_size=50${status ? `&status=${status}` : ""}`),
  reverseReferral: (t: string, id: number, reason: string) =>
    request<unknown>(t, `/referrals/admin/${id}/reverse`, { method: "POST", body: JSON.stringify({ reason }) }),
};
