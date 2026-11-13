// The green slope test (CLAUDE.md: "Measure the new course's greens in the browser against Woodbine's before it ships").
// For every hole of a course it reads the grade (rise over run, central differences over 1 m) on every cell of the green (C.surf is GREEN, within 24 m of the cup,
// 0.5 m apart) of the FINISHED surface, C.h, the ground the ball rolls on, and prints per green: mean, 90th percentile, maximum, the share over 4 % and over 5.6 %
// (a ball stops rolling on its own below mu = 5.6 %), the elevation range and the physics gradient (C.grad). The limits are GREEN_MEAN_MAX 3.3 % and GREEN_P90_MAX 4.4 %;
// this method reads Woodbine's own steepest green (hole 17) at 3.34 % / 4.46 %, so read a few tenths over as inside its accuracy. The edge strip where a green drops
// into a bunker or a creek is real terrain and counts; tools/course's greenwhere analysis (interior vs the cells within 3 m of sand) is in the session notes.
// Run it with Playwright (see CLAUDE.md, Browser testing) against the repo served on localhost:8765:
//   cd <scratch folder with playwright>; LD_LIBRARY_PATH=<libs> node /path/to/tools/green_slope_test.js woodbine augusta
// the green slope test: for every hole of a course, the grade (rise over run) over the green's cells on the finished surface (C.h, the ground the ball rolls on)
const { chromium } = require('playwright');
const keys = process.argv.slice(2);
(async () => {
  const b = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader', '--no-sandbox'] });
  const p = await b.newPage(); const errs = []; p.on('pageerror', e => errs.push(e.message));
  await p.goto('http://localhost:8765/index.html?x=' + Date.now());
  await p.waitForFunction(() => typeof COURSES !== 'undefined' && Object.keys(COURSES).length > 2 && typeof W !== 'undefined' && W.ren, null, { timeout: 120000 });
  for (const key of keys) {
    const rows = await p.evaluate(async (key) => {
      await new Promise((res, rej) => courseLoad(key).then(() => { setCourse(key); res(); }, rej));
      PID.reg = { pid: 'P001', name: 'T' }; PID.key = PID.key || {}; titleOff(); beginRound();
      const out = [], d = .5, g = [0, 0];
      for (let h = 0; h < HOLE_DEFS.length; h++) {
        startHole(h); const C = G.C, cu = C.cup, gr = [], hs = []; let n = 0, mn = 1e9, mx = -1e9;
        for (let x = cu.x - 24; x <= cu.x + 24; x += .5) for (let z = cu.z - 24; z <= cu.z + 24; z += .5) {
          if (Math.hypot(x - cu.x, z - cu.z) > 24 || C.surf(x, z) !== S.GREEN) continue;
          const sx = (C.h(x + d, z) - C.h(x - d, z)) / (2 * d), sz = (C.h(x, z + d) - C.h(x, z - d)) / (2 * d); gr.push(Math.hypot(sx, sz));
          C.grad(x, z, g); hs.push(Math.hypot(g[0], g[1])); const y = C.h(x, z); mn = Math.min(mn, y); mx = Math.max(mx, y);
        }
        gr.sort((a, b) => a - b); hs.sort((a, b) => a - b); const q = (a, f) => a[Math.min(a.length - 1, Math.floor(f * a.length))], mean = a => a.reduce((s, v) => s + v, 0) / a.length;
        out.push({ h: h + 1, n: gr.length, area: Math.round(gr.length * .25), mean: mean(gr), p90: q(gr, .9), max: gr[gr.length - 1], o4: gr.filter(v => v > .04).length / gr.length, o56: gr.filter(v => v > .056).length / gr.length, gmean: mean(hs), gp90: q(hs, .9), drop: mx - mn });
      }
      return out;
    }, key);
    console.log('=== ' + key + '   (limits: mean 3.3 %, p90 4.4 %; a ball stops rolling on its own below mu 5.6 %)');
    console.log('hole  area m2   mean%   p90%   max%   >4%   >5.6%   elevation range   physics-grad mean/p90');
    let wm = 0, wp = 0, bad = [];
    for (const r of rows) { const f = v => (100 * v).toFixed(1).padStart(5); console.log(`${String(r.h).padStart(3)}   ${String(r.area).padStart(6)}   ${f(r.mean)}  ${f(r.p90)}  ${f(r.max)}  ${(100 * r.o4).toFixed(0).padStart(3)}%  ${(100 * r.o56).toFixed(0).padStart(4)}%     ${(r.drop).toFixed(2).padStart(5)} m           ${f(r.gmean)}/${f(r.gp90)}`); wm = Math.max(wm, r.mean); wp = Math.max(wp, r.p90); if (r.mean > .033 || r.p90 > .044) bad.push(r.h); }
    console.log(`worst mean ${(100 * wm).toFixed(2)} %, worst p90 ${(100 * wp).toFixed(2)} %; over a limit: ${bad.length ? bad.join(', ') : 'none'}`);
  }
  console.log('errors', errs.join(' | ') || 'none'); await b.close();
})();
