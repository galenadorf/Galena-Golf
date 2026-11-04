// Offline play. Keeps every file solo play needs, so an installed (or once-visited) game starts and plays with no connection.
// Live multiplayer (MQTT brokers) and the world leaderboard (GitHub) are other origins: they're never intercepted and simply
// fail while offline. The deploy stamps BUILD, so each deploy gets a fresh cache and the old one is dropped.
const BUILD = '__BUILD__';
const CACHE = 'galena-' + BUILD;
const FONTS = ['barlow-latin', 'barlow-latin-ext', 'barlow-vietnamese'].flatMap(f => [500, 600, 700].map(w => `${f}-${w}`))
  .concat(['oswald-latin', 'oswald-latin-ext', 'oswald-vietnamese', 'oswald-cyrillic', 'oswald-cyrillic-ext'])
  .map(f => `fonts/${f}.woff2`);
const CORE = ['./', 'manifest.webmanifest', 'icon.svg', 'icon-192.png', 'icon-512.png', 'icon-maskable-512.png', 'apple-touch-icon.png', 'crest.png',
  'sounds/driver.mp3', 'sounds/wood.mp3', 'sounds/iron.mp3', 'sounds/wedge.mp3', 'sounds/putter.mp3', 'sounds/cup.mp3', 'sounds/truckhorn.mp3', 'sounds/truckrumble.mp3', 'sounds/cartmusic.mp3', 'sounds/plane.mp3', 'sounds/cow1.mp3', 'sounds/cow2.mp3', 'sounds/cow3.mp3', ...[1, 2, 3, 4, 5].map(i => `sounds/bird${i}.mp3`), ...[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19].map(i => `sounds/fart${i}.mp3`), 'vendor/three.r128.min.js', 'vendor/mqtt.5.10.1.min.js', 'fonts/fonts.css', ...FONTS];

// every course in courses/courses.json is kept too (courses/<key>.js), so any course plays offline, not only the ones opened so far
const COURSE_FILES = () => fetch(new Request('courses/courses.json', { cache: 'reload' })).then(r => r.json()).then(j => j.courses.map(c => `courses/${c.key}.js`));
// A deploy changes little, so a new build does not download everything again. tools/pages_hashes.py stamps HASHES (path -> hash of every file of this deploy; a local
// copy has none and fetches all); each cache keeps its build's list under HASH_KEY, and a file whose hash has not changed is copied over from the older cache, the song
// a player has already heard with it. An install that fails part way leaves the old worker running and keeps what it got, so the next try fetches only the rest.
const HASHES = '__HASHES__', HASH_KEY = 'hashes.json', STAMPED = typeof HASHES === 'object';
const relPath = url => new URL(url).pathname.slice(new URL(self.registration.scope).pathname.length);
async function installFiles() {
  const cache = await caches.open(CACHE);
  if (STAMPED) for (const name of await caches.keys()) {
    if (!name.startsWith('galena-') || name === CACHE) continue;
    const old = await caches.open(name), list = await old.match(HASH_KEY); if (!list) continue;
    const had = await list.json();
    for (const req of await old.keys()) {
      const p = relPath(req.url);
      if (p !== HASH_KEY && HASHES[p] && had[p] === HASHES[p] && !(await cache.match(p))) await cache.put(p, await old.match(req));
    }
  }
  const files = CORE.concat('courses/courses.json', await COURSE_FILES()), todo = [];
  for (const f of files) if (f === './' || !STAMPED || !(await cache.match(f))) todo.push(f);
  const worker = async () => {
    for (let f; (f = todo.pop());) {
      const r = await fetch(new Request(f, { cache: 'reload' })); if (!r.ok) throw new Error(f + ': ' + r.status);
      await cache.put(f, r);
    }
  };
  await Promise.all([1, 2, 3, 4, 5, 6].map(worker));
  if (STAMPED) await cache.put(HASH_KEY, new Response(JSON.stringify(HASHES)));
}
self.addEventListener('install', e => { e.waitUntil(installFiles().then(() => self.skipWaiting())); });
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
  // A file the page asked for with another build's ?v= (a new page while the old worker still runs, right after a deploy):
  // the network, so the page never gets the old build's courses.json or course data; the cached copy only when offline.
  const v = url.searchParams.get('v');
  if (v && v !== BUILD) { e.respondWith(fetch(req).catch(() => caches.match(req, { ignoreSearch: true }))); return; }
  // Everything else: cache first, filling the cache with anything not listed above.
  e.respondWith(caches.match(req, { ignoreSearch: true }).then(hit => hit || fetch(req).then(r => {
    if (r.ok) { const cp = r.clone(); caches.open(CACHE).then(c => c.put(req, cp)); }
    return r;
  })));
});
