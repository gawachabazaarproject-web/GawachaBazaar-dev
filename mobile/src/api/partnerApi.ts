import { apiClient } from "./client";

export type AssignmentStatus =
  | "ASSIGNED"
  | "ACCEPTED"
  | "PICKED_UP"
  | "OUT_FOR_DELIVERY"
  | "DELIVERED"
  | "FAILED"
  | "REJECTED"
  | "CANCELLED";

export interface PartnerMe {
  user_id: number;
  name: string | null;
  status: string;
  availability: "OFFLINE" | "AVAILABLE" | "ON_DELIVERY";
  vehicle_type: string;
  vehicle_number: string | null;
  phone: string | null;
  active_assignments: number;
  delivered_today: number;
  earned_today: string;
}

export interface Assignment {
  id: number;
  order_id: number;
  order_number: string;
  status: AssignmentStatus;
  assigned_at: string;
  delivered_at: string | null;
  close_reason: string | null;
  cod_status: "NOT_APPLICABLE" | "COD_PENDING" | "COD_COLLECTED" | "COD_FAILED";
  cod_expected_amount: string;
  cod_collected_amount: string | null;
  customer_name: string | null;
  address: {
    address_line_1: string;
    address_line_2: string | null;
    city: string;
    state: string | null;
    postal_code: string | null;
    latitude: number | null;
    longitude: number | null;
  } | null;
  items: { name: string; quantity: string; unit: string | null }[];
  maps_url: string | null;
  earning_amount: string | null;
}

export interface AssignmentList {
  items: Assignment[];
  total: number;
  page: number;
  page_size: number;
}

export interface Earnings {
  total: string;
  count: number;
  items: { id: number; order_id: number; amount: string; billable_km: number; created_at: string }[];
}

const B = "/delivery-partner";

export const partnerApi = {
  me: () => apiClient.get<PartnerMe>(`${B}/me`).then((r) => r.data),
  setAvailability: (availability: "OFFLINE" | "AVAILABLE") =>
    apiClient.patch<PartnerMe>(`${B}/me/availability`, { availability }).then((r) => r.data),
  list: (scope: "active" | "history", status?: AssignmentStatus) =>
    apiClient
      .get<AssignmentList>(`${B}/assignments`, { params: { scope, status, page_size: 50 } })
      .then((r) => r.data),
  get: (id: number) => apiClient.get<Assignment>(`${B}/assignments/${id}`).then((r) => r.data),
  act: (id: number, action: "accept" | "pickup" | "out-for-delivery") =>
    apiClient.post<Assignment>(`${B}/assignments/${id}/${action}`, {}).then((r) => r.data),
  reject: (id: number, reason: string) =>
    apiClient.post<Assignment>(`${B}/assignments/${id}/reject`, { reason }).then((r) => r.data),
  fail: (id: number, reason: string) =>
    apiClient.post<Assignment>(`${B}/assignments/${id}/fail`, { reason }).then((r) => r.data),
  deliver: (id: number, codCollectedAmount?: string) =>
    apiClient
      .post<Assignment>(`${B}/assignments/${id}/deliver`, {
        cod_collected_amount: codCollectedAmount ?? null,
      })
      .then((r) => r.data),
  location: (id: number, latitude: number, longitude: number, accuracy?: number | null) =>
    apiClient
      .post(`${B}/assignments/${id}/location`, { latitude, longitude, accuracy_m: accuracy ?? null })
      .then(() => undefined),
  earnings: () => apiClient.get<Earnings>(`${B}/earnings`, { params: { page_size: 20 } }).then((r) => r.data),
};
