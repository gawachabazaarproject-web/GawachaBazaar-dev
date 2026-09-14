import { apiClient } from "./client";
import { CategoryDetailResponse, CategoryListResponse, ProductListResponse, ProductResponse } from "@/types/api";

export interface ListProductsParams {
  categoryId?: number;
  q?: string;
  page?: number;
  pageSize?: number;
}

export const catalogApi = {
  listCategories: (parentId?: number) =>
    apiClient
      .get<CategoryListResponse>("/catalog/categories", {
        params: { parent_id: parentId, page_size: 100 },
      })
      .then((r) => r.data.items),

  getCategory: (id: number) =>
    apiClient.get<CategoryDetailResponse>(`/catalog/categories/${id}`).then((r) => r.data),

  listProducts: (params: ListProductsParams = {}) =>
    apiClient
      .get<ProductListResponse>("/catalog/products", {
        params: {
          category_id: params.categoryId,
          q: params.q,
          page: params.page ?? 1,
          page_size: params.pageSize ?? 20,
        },
      })
      .then((r) => r.data),

  getProduct: (id: number) =>
    apiClient.get<ProductResponse>(`/catalog/products/${id}`).then((r) => r.data),
};
