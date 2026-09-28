/**
 * Types mirror backend/app/schemas/ad.py field-for-field. An Ad is pure
 * display/link content for the mobile app's brand-ads carousel - no
 * pricing or redemption logic (that's Promotion, a separate domain).
 */

export interface AdminAdListItem {
  id: number;
  brand_name: string;
  image_url: string;
  link_url: string | null;
  display_order: number;
  status: string;
  created_at: string;
}

export interface AdminAdDetail extends AdminAdListItem {
  updated_at: string;
}

export interface CreateAdPayload {
  brand_name: string;
  link_url?: string;
  display_order: number;
  file: File;
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

export class AdApiError extends Error {
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
      ...(init.body && !(init.body instanceof FormData) ? { "Content-Type": "application/json" } : {}),
      Authorization: `Bearer ${accessToken}`,
      ...init.headers,
    },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new AdApiError(response.status, body?.message ?? "Something went wrong.");
  }
  if (response.status === 204) return undefined as T;
  return response.json();
}

export async function fetchAds(accessToken: string): Promise<AdminAdListItem[]> {
  return request(accessToken, "/ads/admin");
}

export async function createAd(accessToken: string, payload: CreateAdPayload): Promise<AdminAdDetail> {
  const form = new FormData();
  form.append("brand_name", payload.brand_name);
  if (payload.link_url) form.append("link_url", payload.link_url);
  form.append("display_order", String(payload.display_order));
  form.append("file", payload.file);
  return request(accessToken, "/ads/admin", { method: "POST", body: form });
}

export async function replaceAdImage(accessToken: string, id: number, file: File): Promise<AdminAdDetail> {
  const form = new FormData();
  form.append("file", file);
  return request(accessToken, `/ads/admin/${id}/image`, { method: "POST", body: form });
}

export async function updateAd(
  accessToken: string,
  id: number,
  payload: Partial<{ brand_name: string; link_url: string; display_order: number; status: string }>,
): Promise<AdminAdDetail> {
  return request(accessToken, `/ads/admin/${id}`, { method: "PATCH", body: JSON.stringify(payload) });
}

export async function deleteAd(accessToken: string, id: number): Promise<void> {
  await request(accessToken, `/ads/admin/${id}`, { method: "DELETE" });
}
