// Validation of the competition definitions (events, tournaments, seasons), shared by .github/workflows/competitions.yml and tested by hand with node.
// An item is plain data: { id, kind, name, desc, start, end, invite, pals, hcp, points, parent, ... } (see CLAUDE.md, "Events, tournaments and seasons").
const KINDS = { ev: 'event', tn: 'tournament', ss: 'season' };
const PARENT_KIND = { event: 'tournament', tournament: 'season', season: null };
const FORMATS = ['stroke', 'stableford', 'match', 'skins', 'bestball', 'scramble'];
const PLAYS = ['live', 'batched', 'either'];
const TEAM_FORMATS = ['bestball', 'scramble'];
const int = v => Number.isInteger(v);
const day = s => typeof s === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(s) && !isNaN(Date.parse(s + 'T00:00:00Z')) && new Date(s + 'T00:00:00Z').toISOString().slice(0, 10) === s;
// ctx: { courses: [{key, pars, alpha, engine}], items: {id: item}, players: [{id}] }; returns an error text, or null when the item is good
function validate(it, ctx) {
  if (!it || typeof it !== 'object' || Array.isArray(it)) return 'Not an item.';
  if (typeof it.id !== 'string' || !/^(ev|tn|ss)-[a-z0-9]{4,12}$/.test(it.id)) return 'Bad id.';
  const kind = KINDS[it.id.slice(0, 2)]; if (it.kind !== kind) return 'The id does not match the kind.';
  const name = typeof it.name === 'string' ? it.name.trim() : ''; if (!name || name.length > 40) return 'The name must be 1-40 characters.';
  if (it.desc != null && (typeof it.desc !== 'string' || it.desc.length > 400)) return 'The description is too long (400 characters).';
  if (!day(it.start) || !day(it.end) || it.end < it.start) return 'The dates must be YYYY-MM-DD, the end not before the start.';
  if (it.invite !== 'open') {
    if (!Array.isArray(it.invite) || !it.invite.length || it.invite.length > 200 || !it.invite.every(p => ctx.players.some(q => q.id === p))) return 'The invite list must be "open" or registered player IDs.';
  }
  if (typeof it.pals !== 'boolean') return 'PALS Rules must be on or off.';
  if (it.hcp !== 'gross' && it.hcp !== 'net') return 'Handicap must be gross or net.';
  if (!Array.isArray(it.points) || it.points.length > 30 || !it.points.every(p => int(p) && p >= 0 && p <= 10000)) return 'The points table must be up to 30 whole numbers.';
  if (it.kind !== 'season' && !FORMATS.includes(it.format)) return 'Unknown play format.';
  if (it.kind !== 'season' && !PLAYS.includes(it.play)) return 'Play must be live, batched or either.';
  if (it.kind !== 'season') {
    const t = it.team; if (!int(t) || t < 1 || t > 4 || (TEAM_FORMATS.includes(it.format) ? t < 2 : t !== 1)) return 'The team size does not fit the format.';
  }
  if (it.kind === 'event') {
    if (!Array.isArray(it.card) || !it.card.length || it.card.length > 72) return 'An event has 1-72 holes.';
    for (const h of it.card) {
      const c = h && ctx.courses.find(x => x.key === h.c);
      if (!c || (c.engine && c.engine.disc)) return 'Unknown course in the card.';
      if (c.alpha) return c.key + ' is still in alpha: events cannot use it yet.';
      if (!int(h.h) || h.h < 1 || h.h > c.pars.length) return 'Bad hole number in the card.';
    }
  } else if (it.card != null) return 'Only an event has a card.';
  if (it.kind === 'season') {
    if (!int(it.countBest) || it.countBest < 0 || it.countBest > 50) return 'Count-best must be 0 (all) to 50.';
  }
  if (it.parent != null) {
    const want = PARENT_KIND[it.kind], p = ctx.items[it.parent];
    if (!want) return 'A season has no parent.';
    if (!p || p.kind !== want) return 'The parent must be an existing ' + want + '.';
    if (it.start < p.start || it.end > p.end) return 'The dates must fall inside the ' + want + "'s dates (" + p.start + ' to ' + p.end + ').';
  }
  return null;
}
const indexRow = it => ({ id: it.id, kind: it.kind, name: it.name.trim(), start: it.start, end: it.end, parent: it.parent || null });
const children = (id, items) => Object.values(items).filter(x => x.parent === id);
module.exports = { validate, indexRow, children, FORMATS, PLAYS };
