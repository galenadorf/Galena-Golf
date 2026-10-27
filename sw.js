// Offline play. Keeps every file solo play needs, so an installed (or once-visited) game starts and plays with no connection.
// Live multiplayer (MQTT brokers) and the world leaderboard (GitHub) are other origins: they're never intercepted and simply
// fail while offline. The deploy stamps BUILD, so each deploy gets a fresh cache and the old one is dropped.
const BUILD = '__BUILD__';
const CACHE = 'galena-' + BUILD;
const FONTS = ['barlow-latin', 'barlow-latin-ext', 'barlow-vietnamese'].flatMap(f => [500, 600, 700].map(w => `${f}-${w}`))
  .concat(['oswald-latin', 'oswald-latin-ext', 'oswald-vietnamese', 'oswald-cyrillic', 'oswald-cyrillic-ext'])
  .map(f => `fonts/${f}.woff2`);
const CORE = ['./', 'manifest.webmanifest', 'icon.svg', 'icon-192.png', 'icon-512.png', 'icon-maskable-512.png', 'apple-touch-icon.png', 'crest.png',
  'sounds/driver.mp3', 'sounds/wood.mp3', 'sounds/iron.mp3', 'sounds/wedge.mp3', 'sounds/putter.mp3', 'sounds/cup.mp3', 'sounds/truckhorn.mp3', 'sounds/truckrumble.mp3', 'sounds/cartmusic.mp3', ...[1, 2, 3, 4, 5, 6, 7, 8].map(i => `sounds/fart${i}.mp3`), 'vendor/three.r128.min.js', 'vendor/mqtt.5.10.1.min.js', 'fonts/fonts.css', ...FONTS];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(CORE.map(u => new Request(u, { cache: 'reload' })))).then(() => self.skipWaiting()));
});
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k.startsWith('galena-') && k !== CACHE).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});
self.addEventListener('fetch', e => {
  const req = e.request, url = new URL(req.url);
  if (req.method !== 'GET' || url.origin !== location.origin || url.pathname.endsWith('/version.txt')) return;
  if (req.mode === 'navigate') {
    // The page: network first so a deploy shows up at once; the cached copy after 4 s or when offline.
    const net = fetch(req).then(r => { if (r.ok) { const cp = r.clone(); caches.open(CACHE).then(c => c.put('./', cp)); } return r; });
    const cached = () => caches.match('./').then(r => r || net);
    e.respondWith(Promise.race([net, new Promise((ok, no) => setTimeout(no, 4000))]).catch(cached));
    return;
  }
  // Everything else: cache first, filling the cache with anything not listed above.
  e.respondWith(caches.match(req, { ignoreSearch: true }).then(hit => hit || fetch(req).then(r => {
    if (r.ok) { const cp = r.clone(); caches.open(CACHE).then(c => c.put(req, cp)); }
    return r;
  })));
});
