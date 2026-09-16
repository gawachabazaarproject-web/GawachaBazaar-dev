/**
 * Types mirror backend/app/schemas/admin_catalog.py's category schemas
 * field-for-field. `image_url` is Cloudinary-backed (see
 * uploadCategoryImage/deleteCategoryImage below) - there is still no
 * sort_order/is_featured/SEO column on Category in the backend, so those
 * stay absent here rather than a fabricated default, matching the
 * honest-gap pattern already used in Products (Merchandising/Reviews).
 */

export interface AdminCategoryListItem {
  id: number;
  name: string;
  slug: string;
  description: string | null;
  image_url: string | null;
  parent_id: number | null;
  parent_name: string | null;
  status: string;
  product_count: number;
  child_count: number;
  created_at: string;
  updated_at: string;
}

export interface AdminCategoryListResponse {
  items: AdminCategoryListItem[];
  page: number;
  page_size: number;
  total: number;
}

export interface CategoryRef {
  id: number;
  name: string;
  slug: string;
  description: string | null;
  image_url: string | null;
  parent_id: number | null;
  status: string;
  created_at: string;
}

export interface AdminCategoryDetail {
  id: number;
  name: string;
  slug: string;
  description: string | null;
  image_url: string | null;
  parent_id: number | null;
  parent_name: string | null;
  status: string;
  product_count: number;
  created_at: string;
  updated_at: string;
  children: CategoryRef[];
}

export interface CategoryActivityEntry {
  id: number;
  action: string;
  resource_type: string;
  resource_id: number;
  previous_state: string | null;
  new_state: string | null;
  reason: string | null;
  admin_name: string;
  created_at: string;
}

export const CATEGORY_STATUSES = ["ACTIVE", "INACTIVE", "ARCHIVED"] as const;

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

export class CategoryApiError extends Error {
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
    throw new CategoryApiError(response.status, body?.message ?? "Something went wrong.");
  }
  return response.json();
}

export interface AdminCategoryListParams {
  page?: number;
  page_size?: number;
  status?: string;
  parent_id?: number;
  q?: string;
}

export async function fetchAdminCategories(
  accessToken: string,
  params: AdminCategoryListParams,
): Promise<AdminCategoryListResponse> {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== "") search.set(key, String(value));
  });
  return request(accessToken, `/catalog/categories/admin?${search.toString()}`);
}

export async function fetchAdminCategoryDetail(accessToken: string, id: number): Promise<AdminCategoryDetail> {
  return request(accessToken, `/catalog/categories/admin/${id}`);
}

export async function fetchCategoryActivity(accessToken: string, id: number): Promise<CategoryActivityEntry[]> {
  const result = await request<{ items: CategoryActivityEntry[] }>(
    accessToken,
    `/catalog/categories/admin/${id}/activity`,
  );
  return result.items;
}

export interface CreateCategoryPayload {
  name: string;
  slug: string;
  description?: string | null;
  parent_id?: number | null;
  status: string;
}

export async function createCategory(accessToken: string, payload: CreateCategoryPayload) {
  return request<CategoryRef>(accessToken, "/catalog/categories", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export interface UpdateCategoryPayload {
  name?: string;
  slug?: string;
  description?: string | null;
  parent_id?: number | null;
  status?: string;
}

export async function updateCategory(accessToken: string, id: number, payload: UpdateCategoryPayload) {
  return request<CategoryRef>(accessToken, `/catalog/categories/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

/** Cloudinary-backed upload (see backend/app/services/image_upload.py) -
 * a multipart POST, so this bypasses `request()`'s JSON Content-Type
 * (the browser must set its own multipart boundary header). */
export async function uploadCategoryImage(accessToken: string, id: number, file: File): Promise<CategoryRef> {
  const form = new FormData();
  form.append("file", file);

  const response = await fetch(`${API_BASE_URL}/catalog/categories/${id}/image`, {
    method: "POST",
    headers: { Authorization: `Bearer ${accessToken}` },
    body: form,
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new CategoryApiError(response.status, body?.message ?? "Upload failed.");
  }
  return response.json();
}

export async function deleteCategoryImage(accessToken: string, id: number): Promise<CategoryRef> {
  return request<CategoryRef>(accessToken, `/catalog/categories/${id}/image`, { method: "DELETE" });
}
