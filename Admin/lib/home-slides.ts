/** Types mirror backend/app/schemas/home_slide.py - the slides of the
 * mobile app's big hero carousel on Home. */

export interface HomeSlide {
  id: number;
  label: string;
  title: string;
  script_suffix: string | null;
  body: string;
  image_url: string;
  cta_label: string;
  link_url: string | null;
  display_order: number;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface HomeSlideFields {
  label: string;
  title: string;
  script_suffix: string;
  body: string;
  cta_label: string;
  link_url: string;
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

export class HomeSlideApiError extends Error {
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
    throw new HomeSlideApiError(response.status, body?.message ?? "Something went wrong.");
  }
  if (response.status === 204) return undefined as T;
  return response.json();
}

export const fetchHomeSlides = (token: string) => request<HomeSlide[]>(token, "/home-slides/admin");

export function createHomeSlide(
  token: string,
  fields: HomeSlideFields & { display_order: number; file: File },
): Promise<HomeSlide> {
  const form = new FormData();
  form.append("label", fields.label);
  form.append("title", fields.title);
  form.append("script_suffix", fields.script_suffix);
  form.append("body", fields.body);
  form.append("cta_label", fields.cta_label);
  if (fields.link_url) form.append("link_url", fields.link_url);
  form.append("display_order", String(fields.display_order));
  form.append("file", fields.file);
  return request(token, "/home-slides/admin", { method: "POST", body: form });
}

export function updateHomeSlide(
  token: string,
  id: number,
  payload: Partial<HomeSlideFields & { display_order: number; status: string }>,
): Promise<HomeSlide> {
  return request(token, `/home-slides/admin/${id}`, { method: "PATCH", body: JSON.stringify(payload) });
}

export function replaceHomeSlideImage(token: string, id: number, file: File): Promise<HomeSlide> {
  const form = new FormData();
  form.append("file", file);
  return request(token, `/home-slides/admin/${id}/image`, { method: "POST", body: form });
}

export const deleteHomeSlide = (token: string, id: number) =>
  request<void>(token, `/home-slides/admin/${id}`, { method: "DELETE" });
