import { useInfiniteQuery, useQueries, useQuery } from "@tanstack/react-query";
import { adsApi, catalogApi, homeSlidesApi, ListProductsParams } from "@/api";

export function useAds() {
  return useQuery({
    queryKey: ["ads"],
    queryFn: () => adsApi.listActive(),
    staleTime: 5 * 60_000,
  });
}

export function useHomeSlides() {
  return useQuery({
    queryKey: ["home-slides"],
    queryFn: () => homeSlidesApi.listActive(),
    staleTime: 60_000,
  });
}

export function useCategories() {
  return useQuery({
    queryKey: ["categories"],
    queryFn: () => catalogApi.listCategories(),
    staleTime: 5 * 60_000,
  });
}

/** The Home screen's category grid (admin-controlled visibility + order). */
export function useHomeCategories() {
  return useQuery({
    queryKey: ["categories", "home"],
    queryFn: () => catalogApi.listCategories(undefined, { homepage: true }),
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

/** Every product of one category (the API folds in its subcategories),
 * fetched page by page. The Category screen must not slice the global list:
 * that is capped at 100 items, so products past the cap showed "0 items". */
export function useCategoryProducts(categoryId: number | null) {
  return useQuery({
    queryKey: ["products", "category-all", categoryId],
    enabled: categoryId !== null && !Number.isNaN(categoryId),
    staleTime: 60_000,
    queryFn: async () => {
      const first = await catalogApi.listProducts({ categoryId: categoryId as number, page: 1, pageSize: 100 });
      const items = [...first.items];
      for (let page = 2; items.length < first.total && page <= 20; page++) {
        const next = await catalogApi.listProducts({ categoryId: categoryId as number, page, pageSize: 100 });
        if (next.items.length === 0) break;
        items.push(...next.items);
      }
      return { ...first, items };
    },
  });
}

/** Product ids listed under each subcategory. A product can sit in extra
 * categories, but list items only carry their main category_id, so sections
 * must ask the API (which knows every placement) rather than infer it. */
export function useSubcategoryProductIds(childIds: number[]) {
  return useQueries({
    queries: childIds.map((id) => ({
      queryKey: ["products", "subcategory-ids", id],
      staleTime: 60_000,
      queryFn: async () => {
        const res = await catalogApi.listProducts({ categoryId: id, page: 1, pageSize: 100 });
        return res.items.map((p) => p.id);
      },
    })),
    combine: (results) => {
      const map = new Map<number, Set<number>>();
      results.forEach((r, i) => {
        if (r.data) map.set(childIds[i], new Set(r.data));
      });
      return map;
    },
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
