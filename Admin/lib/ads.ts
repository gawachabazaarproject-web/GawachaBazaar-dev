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
  title: string | null;
  subtitle: string | null;
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
  title?: string;
  subtitle?: string;
  display_order: number;
  file: File;
}

/** The mobile ads card keeps this exact aspect ratio on every phone
 * (mobile/src/components/home/BrandAdsCarousel.tsx), so an image that
 * matches it is never cropped. */
export const AD_IMAGE = {
  width: 1200,
  height: 500,
  ratioLabel: "12:5",
  ratio: 12 / 5,
  tolerance: 0.03,
} as const;

/** Resolves to an error message, or null when the image is suitable. */
export function validateAdImage(file: File): Promise<string | null> {
  return new Promise((resolve) => {
    const url = URL.createObjectURL(file);
    const img = new Image();
    img.onload = () => {
      URL.revokeObjectURL(url);
      const { naturalWidth: w, naturalHeight: h } = img;
      if (Math.abs(w / h - AD_IMAGE.ratio) / AD_IMAGE.ratio > AD_IMAGE.tolerance) {
        resolve(
          `This image is ${w} x ${h} px (${(w / h).toFixed(2)}:1). Ads must be ${AD_IMAGE.width} x ${AD_IMAGE.height} px (${AD_IMAGE.ratioLabel}) so nothing gets cropped.`,
        );
      } else if (w < 600) {
        resolve(`This image is only ${w} px wide and would look blurry. Use ${AD_IMAGE.width} x ${AD_IMAGE.height} px.`);
      } else {
        resolve(null);
      }
    };
    img.onerror = () => {
      URL.revokeObjectURL(url);
      resolve("Could not read this image.");
    };
    img.src = url;
  });
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
  if (payload.title) form.append("title", payload.title);
  if (payload.subtitle) form.append("subtitle", payload.subtitle);
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
  payload: Partial<{ brand_name: string; link_url: string; title: string; subtitle: string; display_order: number; status: string }>,
): Promise<AdminAdDetail> {
  return request(accessToken, `/ads/admin/${id}`, { method: "PATCH", body: JSON.stringify(payload) });
}

export async function deleteAd(accessToken: string, id: number): Promise<void> {
  await request(accessToken, `/ads/admin/${id}`, { method: "DELETE" });
}
