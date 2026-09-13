import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { catalogApi, ListProductsParams } from "@/api";

export function useCategories() {
  return useQuery({
    queryKey: ["categories"],
    queryFn: () => catalogApi.listCategories(),
    staleTime: 5 * 60_000,
  });
}

export function useCategory(id: number | null) {
  return useQuery({
    queryKey: ["category", id],
    queryFn: () => catalogApi.getCategory(id as number),
    enabled: id !== null,
  });
}

export function useProduct(id: number | null) {
  return useQuery({
    queryKey: ["product", id],
    queryFn: () => catalogApi.getProduct(id as number),
    enabled: id !== null,
  });
}

const PAGE_SIZE = 20;

/** Paginated product listing, used by Category and Search screens alike -
 * `q` and `categoryId` are mutually usable (the backend supports both
 * together, though the UI only ever sets one at a time). */
export function useProducts(params: Omit<ListProductsParams, "page" | "pageSize">) {
  return useInfiniteQuery({
    queryKey: ["products", params],
    queryFn: ({ pageParam }) => catalogApi.listProducts({ ...params, page: pageParam, pageSize: PAGE_SIZE }),
    initialPageParam: 1,
    getNextPageParam: (lastPage) => {
      const loaded = lastPage.page * lastPage.page_size;
      return loaded < lastPage.total ? lastPage.page + 1 : undefined;
    },
    enabled: params.q === undefined || params.q.length > 0,
  });
}

/** Full catalog in one request (safe given this app's small product
 * count) - used only for client-side illustrative grouping (Categories'
 * department tiles, Search's "Pairs with X" rail), never for the main
 * paginated product grid, which always goes through `useProducts`. */
export function useAllProducts() {
  return useQuery({
    queryKey: ["products", "all"],
    queryFn: () => catalogApi.listProducts({ page: 1, pageSize: 100 }),
    staleTime: 60_000,
  });
}
