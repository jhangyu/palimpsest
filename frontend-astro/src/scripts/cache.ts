/*
---
name: cache
description: "Simple in-memory TTL cache for API responses; avoids redundant fetches for infrequently-changing data such as site lists and provider lists"
type: script
target:
  layer: frontend
  domain: cache
spec_doc: null
test_file: null
functions:
  - name: getCached
    line: 33
    purpose: "Retrieve cached value by key; returns null if entry is missing or expired beyond TTL"
  - name: setCache
    line: 43
    purpose: "Store a typed value in cache with the current timestamp"
  - name: invalidateCache
    line: 47
    purpose: "Delete a specific cache entry by key, or clear all entries if key is omitted"
---
*/
/**
 * cache.ts — Simple in-memory TTL cache for API responses.
 *
 * Intended for infrequently-changing data (e.g. sites list, providers list)
 * that is fetched on multiple pages but rarely mutated.
 */

interface CacheEntry<T> {
  data: T
  timestamp: number
}

const cache = new Map<string, CacheEntry<unknown>>()
const DEFAULT_TTL = 60_000

export function getCached<T>(key: string, ttl = DEFAULT_TTL): T | null {
  const entry = cache.get(key)
  if (!entry) return null
  if (Date.now() - entry.timestamp > ttl) {
    cache.delete(key)
    return null
  }
  return entry.data as T
}

export function setCache<T>(key: string, data: T): void {
  cache.set(key, { data, timestamp: Date.now() })
}

export function invalidateCache(key?: string): void {
  if (key) cache.delete(key)
  else cache.clear()
}
