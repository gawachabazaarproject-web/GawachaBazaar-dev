/**
 * TypeScript mirrors of the backend Pydantic response/request schemas.
 * Kept in sync manually against `backend/app/schemas/*.py` - see
 * docs/API.md for how to regenerate/verify against the live OpenAPI
 * schema. Decimal fields arrive as strings (backend never sends floats
 * for money/quantity) - see src/utils/money.ts for parsing.
 */

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------

export interface UserResponse {
  id: number;
  name: string;
  email: string;
  phone: string;
  status: string;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user: UserResponse;
}

export interface RefreshTokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface RegisterPayload {
  name: string;
  email: string;
  phone: string;
  password: string;
}

export interface LoginPayload {
  identifier: string;
  password: string;
}

// ---------------------------------------------------------------------------
// Address
// ---------------------------------------------------------------------------

export interface AddressResponse {
  id: number;
  label: string;
  address_line_1: string;
  address_line_2: string | null;
  city: string;
  state: string;
  postal_code: string;
  latitude: string | null;
  longitude: string | null;
  is_default: boolean;
  created_at: string;
  updated_at: string;
}

export interface AddressListResponse {
  items: AddressResponse[];
}

export interface CreateAddressPayload {
  label: string;
  address_line_1: string;
  address_line_2?: string | null;
  city: string;
  state: string;
  postal_code: string;
  latitude?: number | null;
  longitude?: number | null;
  is_default?: boolean;
}

export type UpdateAddressPayload = Partial<CreateAddressPayload>;

// ---------------------------------------------------------------------------
// Catalog
// ---------------------------------------------------------------------------

export interface CategoryResponse {
  id: number;
  name: string;
  slug: string;
  description: string | null;
  parent_id: number | null;
  status: string;
  created_at: string;
}

export interface CategoryDetailResponse extends CategoryResponse {
  children: CategoryResponse[];
}

export interface CategoryListResponse {
  items: CategoryResponse[];
  page: number;
  page_size: number;
  total: number;
}

export interface PriceResponse {
  id: number;
  variant_id: number;
  price: string;
  currency: string;
  valid_from: string;
  valid_to: string | null;
  is_active: boolean;
}

export interface ProductVariantResponse {
  id: number;
  name: string;
  sku: string;
  unit: string;
  quantity: string;
  status: string;
  current_price: PriceResponse | null;
}

export interface ProductImageResponse {
  id: number;
  image_url: string;
  alt_text: string | null;
  is_primary: boolean;
  sort_order: number;
}

export interface ProductSummaryResponse {
  id: number;
  name: string;
  slug: string;
  category_id: number;
  status: string;
  primary_image_url: string | null;
  starting_price: PriceResponse | null;
  default_variant_id: number | null;
  default_variant_unit: string | null;
  default_variant_quantity: string | null;
}

export interface ProductResponse {
  id: number;
  name: string;
  slug: string;
  description: string | null;
  status: string;
  category: CategoryResponse;
  images: ProductImageResponse[];
  variants: ProductVariantResponse[];
}

export interface ProductListResponse {
  items: ProductSummaryResponse[];
  page: number;
  page_size: number;
  total: number;
}

// ---------------------------------------------------------------------------
// Cart
// ---------------------------------------------------------------------------

export interface CartItemResponse {
  id: number;
  variant_id: number;
  product_id: number;
  product_slug: string;
  primary_image_url: string | null;
  product_name: string;
  variant_name: string;
  sku: string;
  quantity: string;
  unit_price: string | null;
  line_total: string | null;
  currency: string | null;
}

export interface CartResponse {
  id: number | null;
  status: string;
  items: CartItemResponse[];
  total_amount: string | null;
  currency: string | null;
}

// ---------------------------------------------------------------------------
// Orders
// ---------------------------------------------------------------------------

export interface OrderItemResponse {
  id: number;
  variant_id: number;
  product_name: string;
  variant_name: string;
  sku: string;
  unit: string;
  quantity: string;
  unit_price: string;
  total_price: string;
}

export interface OrderAddressResponse {
  address_line_1: string;
  address_line_2: string | null;
  city: string;
  state: string;
  postal_code: string;
  latitude: string | null;
  longitude: string | null;
}

export interface OrderResponse {
  id: number;
  order_number: string;
  status: OrderStatus;
  total_amount: string;
  currency: string;
  placed_at: string;
  created_at: string;
  cancelled_at: string | null;
  cancellation_reason: string | null;
}

export interface OrderDetailResponse extends OrderResponse {
  items: OrderItemResponse[];
  address: OrderAddressResponse | null;
}

export interface OrderListResponse {
  items: OrderResponse[];
  page: number;
  page_size: number;
  total: number;
}

/** Exact backend order_state.py values - the app never invents a status. */
export type OrderStatus = "PENDING" | "CONFIRMED" | "CANCELLED" | "COMPLETED" | "EXPIRED";

/** Exact backend fulfillment_state.py values. */
export type FulfillmentStatus =
  | "PENDING"
  | "PICKING"
  | "PACKED"
  | "READY_FOR_DELIVERY"
  | "ASSIGNED"
  | "OUT_FOR_DELIVERY"
  | "DELIVERED";

export interface CustomerFulfillmentResponse {
  status: FulfillmentStatus;
  delivered_at: string | null;
  created_at: string;
  updated_at: string;
}

// ---------------------------------------------------------------------------
// Payments
// ---------------------------------------------------------------------------

export type PaymentMethod = "UPI" | "COD";

/** Exact backend payment_state.py values. */
export type PaymentStatus = "PENDING" | "PROCESSING" | "PAID" | "FAILED" | "CANCELLED" | "EXPIRED";

export interface PaymentResponse {
  id: number;
  order_id: number;
  payment_method: PaymentMethod;
  status: PaymentStatus;
  amount: string;
  currency: string;
  gateway_name: string | null;
  gateway_order_id: string | null;
  paid_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface PaymentInitiationResponse extends PaymentResponse {
  payment_session_token: string | null;
  upi_intent_uri: string | null;
}

export interface CreatePaymentPayload {
  order_id: number;
  payment_method: PaymentMethod;
}

// ---------------------------------------------------------------------------
// Refunds
// ---------------------------------------------------------------------------

/** Exact backend refund_state.py values. */
export type RefundStatus =
  | "PENDING_APPROVAL"
  | "APPROVED"
  | "REJECTED"
  | "PROCESSING"
  | "REFUNDED"
  | "FAILED";

export interface RefundResponse {
  id: number;
  order_id: number;
  status: RefundStatus;
  amount: string;
  currency: string;
  requested_at: string;
  created_at: string;
  updated_at: string;
}

export interface CancelOrderPayload {
  reason?: string | null;
}

// ---------------------------------------------------------------------------
// Reservation (read-only, informational)
// ---------------------------------------------------------------------------

export interface InventoryReservationResponse {
  id: number;
  order_id: number;
  status: string;
  expires_at: string;
  released_at: string | null;
  created_at: string;
  updated_at: string;
}

// ---------------------------------------------------------------------------
// Bulk / wholesale orders
// ---------------------------------------------------------------------------

/** Exact backend bulk_order.py BusinessType values. */
export type BusinessType =
  | "RESTAURANT"
  | "HOTEL"
  | "CATERER"
  | "RETAILER"
  | "OFFICE"
  | "INSTITUTION"
  | "EVENT"
  | "OTHER";

/** Exact backend bulk_order.py RequestUnit values - deliberately separate
 * from ProductVariant's own `unit` field, since a bulk request can name a
 * unit the catalog variant doesn't use (e.g. requesting "5 CRATE" of a
 * product sold retail by the KG). */
export type RequestUnit = "KG" | "G" | "L" | "ML" | "UNIT" | "DOZEN" | "BOX" | "CRATE";

/** Exact backend bulk_order_state.py values. */
export type BulkOrderRequestStatus =
  | "REQUESTED"
  | "UNDER_REVIEW"
  | "QUOTED"
  | "CUSTOMER_ACCEPTED"
  | "CONVERTED_TO_ORDER"
  | "REJECTED"
  | "CANCELLED"
  | "EXPIRED";

/** Exact backend quote_state.py QuoteVersionStatus values. */
export type QuoteVersionStatus = "DRAFT" | "SENT" | "ACCEPTED" | "REJECTED" | "SUPERSEDED" | "EXPIRED";

export interface BulkCustomerProfileResponse {
  id: number;
  user_id: number;
  business_name: string;
  business_type: BusinessType;
  contact_person: string | null;
  created_at: string;
  updated_at: string;
}

export interface UpsertBulkCustomerProfilePayload {
  business_name: string;
  business_type: BusinessType;
  contact_person?: string | null;
}

export interface CreateBulkOrderRequestItemPayload {
  /** Exactly one of product_id / custom_item_name, matching the
   * backend's model_validator. */
  product_id?: number | null;
  custom_item_name?: string | null;
  requested_quantity: string;
  unit: RequestUnit;
  customer_notes?: string | null;
}

export interface CreateBulkOrderRequestPayload {
  address_id?: number | null;
  requested_delivery_date?: string | null;
  customer_notes?: string | null;
  items: CreateBulkOrderRequestItemPayload[];
}

export interface BulkOrderRequestItemResponse {
  id: number;
  product_id: number | null;
  product_name: string | null;
  custom_item_name: string | null;
  requested_quantity: string;
  unit: RequestUnit;
  customer_notes: string | null;
  created_at: string;
}

export interface BulkOrderRequestAddressResponse {
  address_line_1: string;
  address_line_2: string | null;
  city: string;
  state: string;
  postal_code: string;
}

export interface BulkOrderRequestResponse {
  id: number;
  status: BulkOrderRequestStatus;
  requested_delivery_date: string | null;
  customer_notes: string | null;
  address: BulkOrderRequestAddressResponse | null;
  items: BulkOrderRequestItemResponse[];
  created_at: string;
  updated_at: string;
}

export interface BulkOrderRequestListResponse {
  items: BulkOrderRequestResponse[];
  page: number;
  page_size: number;
  total: number;
}

export interface QuoteItemResponse {
  id: number;
  request_item_id: number;
  variant_id: number;
  variant_name: string;
  sku: string;
  quantity: string;
  unit_price: string;
  total_price: string;
}

export interface QuoteVersionResponse {
  id: number;
  version_number: number;
  status: QuoteVersionStatus;
  currency: string;
  valid_until: string | null;
  admin_notes: string | null;
  items: QuoteItemResponse[];
  created_at: string;
}

export interface QuoteResponse {
  id: number;
  request_id: number;
  versions: QuoteVersionResponse[];
  created_at: string;
  updated_at: string;
}

// ---------------------------------------------------------------------------
// Errors (uniform backend contract)
// ---------------------------------------------------------------------------

export interface ApiErrorBody {
  code: string;
  message: string;
  details: unknown;
}
