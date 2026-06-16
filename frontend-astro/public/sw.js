/* global caches, fetch */
const CACHE = 'palimpsest-ui-r1'

const PRECACHE_URLS = [
  '/',
  '/css/style.min.css'
]

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE).then((cache) => cache.addAll(PRECACHE_URLS))
  )
  self.skipWaiting()
})

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    )
  )
  self.clients.claim()
})

self.addEventListener('fetch', (event) => {
  const { request } = event
  if (request.method !== 'GET') return

  // HTML: network-first
  if (request.headers.get('accept')?.includes('text/html')) {
    event.respondWith(
      fetch(request)
        .then((response) => {
          const clone = response.clone()
          caches.open(CACHE).then((cache) => cache.put(request, clone))
          return response
        })
        .catch(() => caches.match(request))
    )
    return
  }

  // Static assets: cache-first
  event.respondWith(
    caches.match(request).then((cached) => cached || fetch(request))
  )
})
