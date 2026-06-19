/**
 * cache.ts — Simple in-memory TTL cache for API responses.
 *
 * Intended for infrequently-changing data (e.g. sites list, providers list)
 * that is fetched on multiple pages but rarely mutated.
 */

interface CacheEntry<T> {
  data: T;
  timestamp: number;
}

const cache = new Map<string, CacheEntry<unknown>>();
const DEFAULT_TTL = 60_000; // 60 seconds

export function getCached<T>(key: string, ttl = DEFAULT_TTL): T | null {
  const entry = cache.get(key);
  if (!entry) return null;
  if (Date.now() - entry.timestamp > ttl) {
    cache.delete(key);
    return null;
  }
  return entry.data as T;
}

export function setCache<T>(key: string, data: T): void {
  cache.set(key, { data, timestamp: Date.now() });
}

export function invalidateCache(key?: string): void {
  if (key) cache.delete(key);
  else cache.clear();
}
