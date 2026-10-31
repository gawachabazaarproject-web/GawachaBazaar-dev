/**
 * Tiny in-memory cache for admin *reference* data that rarely changes and is
 * re-read by many screens (e.g. the warehouse list). Concurrent callers share
 * one request, a failed request is never cached, and a mutation must call
 * `invalidateMemo` so the next read is fresh. Deliberately not used for orders,
 * payments or stock - operators must always see those live.
 */
const entries = new Map<string, { expires: number; value: Promise<unknown> }>();

export function memoized<T>(key: string, ttlMs: number, load: () => Promise<T>): Promise<T> {
  const hit = entries.get(key);
  if (hit && hit.expires > Date.now()) return hit.value as Promise<T>;
  const value = load().catch((err) => {
    if (entries.get(key)?.value === value) entries.delete(key);
    throw err;
  });
  entries.set(key, { expires: Date.now() + ttlMs, value });
  return value;
}

export function invalidateMemo(prefix = ""): void {
  for (const key of Array.from(entries.keys())) {
    if (key.startsWith(prefix)) entries.delete(key);
  }
}
