const CACHE_NAME = 'anki-creator-v1';
const ASSETS = [
  '/',
  '/static/style.css',
  '/static/images/icon-192.png',
  '/static/images/icon-512.png',
  '/offline.html'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(ASSETS))
  );
});

self.addEventListener('fetch', event => {
  event.respondWith(
    caches.match(event.request)
      .then(response => response || fetch(event.request))
      .catch(() => caches.match('/offline.html'))
  );
});
