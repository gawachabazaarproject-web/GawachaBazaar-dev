/**
 * Types mirror backend/app/schemas/staff.py field-for-field. A "staff
 * member" is not a separate table - it is an existing User holding at
 * least one of ADMIN/HUB_STAFF/OPERATIONS/DELIVERY_PARTNER/SUPPORT (see
 * backend/app/core/roles.py STAFF_ROLES), same convention as Customers.
 */

export const STAFF_ROLES = ["ADMIN", "HUB_STAFF", "OPERATIONS", "DELIVERY_PARTNER", "SUPPORT"] as const;
export const STAFF_STATUSES = ["ACTIVE", "INACTIVE", "SUSPENDED"] as const;

export interface StaffListItem {
  id: number;
  name: string;
  email: string;
  phone: string;
  status: string;
  roles: string[];
  created_at: string;
}

export interface StaffDetail extends StaffListItem {
  updated_at: string;
}

export interface CreateStaffPayload {
  name: string;
  email: string;
  phone: string;
  password: string;
  role: string;
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

export class StaffApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(accessToken: string, path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      ...(init.body ? { "Content-Type": "application/json" } : {}),
      Authorization: `Bearer ${accessToken}`,
      ...init.headers,
    },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new StaffApiError(response.status, body?.message ?? "Something went wrong.");
  }
  if (response.status === 204) return undefined as T;
  return response.json();
}

export async function fetchStaff(accessToken: string): Promise<StaffListItem[]> {
  return request(accessToken, "/staff");
}

export async function fetchStaffDetail(accessToken: string, id: number): Promise<StaffDetail> {
  return request(accessToken, `/staff/${id}`);
}

export async function createStaff(accessToken: string, payload: CreateStaffPayload): Promise<StaffDetail> {
  return request(accessToken, "/staff", { method: "POST", body: JSON.stringify(payload) });
}

export async function assignStaffRole(accessToken: string, id: number, role: string): Promise<StaffDetail> {
  return request(accessToken, `/staff/${id}/roles`, { method: "POST", body: JSON.stringify({ role }) });
}

export async function revokeStaffRole(accessToken: string, id: number, role: string): Promise<StaffDetail> {
  return request(accessToken, `/staff/${id}/roles/${role}`, { method: "DELETE" });
}

export async function setStaffStatus(accessToken: string, id: number, status: string): Promise<StaffDetail> {
  return request(accessToken, `/staff/${id}/status`, { method: "PATCH", body: JSON.stringify({ status }) });
}
