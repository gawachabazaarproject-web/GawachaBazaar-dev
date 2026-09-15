/**
 * Types mirror backend/app/schemas/{admin_catalog,catalog}.py field-for-
 * field. Decimal/money fields are strings (FastAPI serializes Pydantic
 * Decimal as a JSON string) - parse only for display, never for further
 * math (pricing/stock arithmetic happens on the backend only).
 */

export interface Category {
  id: number;
  name: string;
  slug: string;
  description: string | null;
  parent_id: number | null;
  status: string;
  created_at: string;
}

export interface AdminProductListItem {
  id: number;
  name: string;
  slug: string;
  category_id: number;
  category_name: string;
  status: string;
  primary_image_url: string | null;
  price: string | null;
  currency: string | null;
  variant_count: number;
  total_available_stock: string;
  created_at: string;
  updated_at: string;
}

export interface AdminProductListResponse {
  items: AdminProductListItem[];
  page: number;
  page_size: number;
  total: number;
}

export interface PriceInfo {
  id: number;
  variant_id: number;
  price: string;
  currency: string;
  valid_from: string;
  valid_to: string | null;
  is_active: boolean;
}

export interface ProductVariant {
  id: number;
  name: string;
  sku: string;
  unit: string;
  quantity: string;
  status: string;
  current_price: PriceInfo | null;
}

export interface ProductImage {
  id: number;
  image_url: string;
  alt_text: string | null;
  is_primary: boolean;
  sort_order: number;
}

export interface VariantStock {
  variant_id: number;
  variant_name: string;
  sku: string;
  status: string;
  available_quantity: string;
}

export interface AdminProductDetail {
  id: number;
  name: string;
  slug: string;
  description: string | null;
  status: string;
  created_at: string;
  updated_at: string;
  category: Category;
  images: ProductImage[];
  variants: ProductVariant[];
  variant_stock: VariantStock[];
}

export interface ProductActivityEntry {
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

export const VARIANT_UNITS = ["KG", "G", "L", "ML", "UNIT", "DOZEN", "BOX", "PACK"] as const;
export const PRODUCT_STATUSES = ["DRAFT", "ACTIVE", "INACTIVE", "ARCHIVED"] as const;

export interface AdminProductListParams {
  page?: number;
  page_size?: number;
  status?: string;
  category_id?: number;
  q?: string;
  price_min?: string;
  price_max?: string;
  created_from?: string;
  created_to?: string;
  updated_from?: string;
  updated_to?: string;
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

export class CatalogApiError extends Error {
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
    throw new CatalogApiError(response.status, body?.message ?? "Something went wrong.");
  }
  if (response.status === 204) return undefined as T;
  return response.json();
}

export async function fetchCategories(): Promise<Category[]> {
  const response = await fetch(`${API_BASE_URL}/catalog/categories?page=1&page_size=100`);
  if (!response.ok) throw new CatalogApiError(response.status, "Unable to load categories.");
  const data = await response.json();
  return data.items;
}

export async function fetchAdminProducts(
  accessToken: string,
  params: AdminProductListParams,
): Promise<AdminProductListResponse> {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== "") search.set(key, String(value));
  });
  return request(accessToken, `/catalog/products/admin?${search.toString()}`);
}

export async function fetchAdminProductDetail(accessToken: string, id: number): Promise<AdminProductDetail> {
  return request(accessToken, `/catalog/products/admin/${id}`);
}

export async function fetchProductActivity(accessToken: string, id: number): Promise<ProductActivityEntry[]> {
  const result = await request<{ items: ProductActivityEntry[] }>(
    accessToken,
    `/catalog/products/admin/${id}/activity`,
  );
  return result.items;
}

export interface CreateProductPayload {
  category_id: number;
  name: string;
  slug: string;
  description?: string | null;
  status: string;
}

export async function createProduct(accessToken: string, payload: CreateProductPayload) {
  return request<AdminProductDetail>(accessToken, "/catalog/products", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export interface UpdateProductPayload {
  category_id?: number;
  name?: string;
  slug?: string;
  description?: string | null;
  status?: string;
}

export async function updateProduct(accessToken: string, id: number, payload: UpdateProductPayload) {
  return request<AdminProductDetail>(accessToken, `/catalog/products/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export interface CreateVariantPayload {
  name: string;
  sku: string;
  unit: string;
  quantity: string;
  status: string;
}

export async function createVariant(accessToken: string, productId: number, payload: CreateVariantPayload) {
  return request<ProductVariant>(accessToken, `/catalog/products/${productId}/variants`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function updateVariant(
  accessToken: string,
  variantId: number,
  payload: Partial<CreateVariantPayload>,
) {
  return request<ProductVariant>(accessToken, `/catalog/variants/${variantId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function createPrice(
  accessToken: string,
  variantId: number,
  price: string,
  currency: string = "INR",
) {
  return request<PriceInfo>(accessToken, `/catalog/variants/${variantId}/prices`, {
    method: "POST",
    body: JSON.stringify({ price, currency }),
  });
}

export interface CreateImagePayload {
  image_url: string;
  alt_text?: string | null;
  is_primary?: boolean;
  sort_order?: number;
}

export async function createImage(accessToken: string, productId: number, payload: CreateImagePayload) {
  return request<ProductImage>(accessToken, `/catalog/products/${productId}/images`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function updateImage(accessToken: string, imageId: number, payload: Partial<CreateImagePayload>) {
  return request<ProductImage>(accessToken, `/catalog/images/${imageId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function deleteImage(accessToken: string, imageId: number) {
  return request<void>(accessToken, `/catalog/images/${imageId}`, { method: "DELETE" });
}
