/* The tree as an ontology graph: News at the hub, its categories, the topics
   inside them at every depth (AI sits under Technology and has its own), your
   own topics, the sources feeding them -- and dashed links between topics that
   write about similar things. Laid out as a radial tree, then tidied by forces
   (d3-force) so no label covers another and related topics lean together.

   "Similar" is the stories' vectors: a topic's vector is the re-normalised
   mean of the centroids of the stories filed in it or below it (the bundle
   carries them), so two topics are related when their stories point the same
   way. Each is linked to its closest few, ranked rather than cut at a
   threshold -- a comparison needs no scale (CLAUDE.md, "Topics have no
   threshold"). Pure functions only, so the maths is testable without a
   browser. */

import { SimulationLinkDatum, SimulationNodeDatum, forceCollide, forceLink, forceSimulation, forceX, forceY } from 'd3-force';
import { Bundle, ROOT, Story, placesOf } from './data';
import { Profile, Topic, fits } from './state';
import { decodeVector } from './vectors';

/* area: the hub. branch: a topic with others inside it. leaf: one without.
   own: a topic of your own. src: a source. */
export type Kind = 'area' | 'branch' | 'leaf' | 'own' | 'src';
export interface GNode {
  key: string; kind: Kind; label: string;
  x: number; y: number; w: number; h: number; // centre, and size at zoom 1
  depth: number;       // 0 the hub, 1 a category, 2 inside one...
  slug?: string;       // the tree's slug
  parent?: string;     // the tree's parent slug
  top?: string;        // the category it is in, for its colour
  topicId?: string;    // the reader's topic it opens in, if any
  followed: boolean;   // inside something the reader follows
  mine?: boolean;      // one of the reader's topics itself
}
export interface GEdge { a: string; b: string; kind: 'tree' | 'rel' | 'src'; strength?: number }
export interface Options { scope: 'mine' | 'all'; related: boolean; sources: boolean }

const FONT = { leaf: 11.5, src: 11 } as const;
const SOURCES_PER_TOPIC = 4;
export const sizeOf = (kind: Kind, depth: number, label: string) => {
  if (kind === 'area') return { w: 64, h: 34 };
  const n = Math.min(label.length, 26);
  if (kind === 'leaf') return { w: n * FONT.leaf * 0.56 + 18, h: 18 };   // a dot and its name
  if (kind === 'src') return { w: n * FONT.src * 0.56 + 22, h: 22 };
  const big = depth <= 1 || kind === 'own';
  return { w: n * (big ? 13 : 12) * 0.56 + 26, h: big ? 30 : 26 };
};

/* Sum into a float vector, then normalise: the mean direction of many. */
function meanOf(vectors: Int8Array[]): Float32Array | null {
  if (!vectors.length) return null;
  const out = new Float32Array(vectors[0].length);
  for (const v of vectors) for (let i = 0; i < v.length; i += 1) out[i] += v[i];
  let n = 0;
  for (let i = 0; i < out.length; i += 1) n += out[i] * out[i];
  n = Math.sqrt(n) || 1;
  for (let i = 0; i < out.length; i += 1) out[i] /= n;
  return out;
}

export function cos(a: Float32Array, b: Float32Array): number {
  let d = 0;
  for (let i = 0; i < a.length; i += 1) d += a[i] * b[i];
  return d; // both are unit vectors
}

/* A vector for every topic in the tree, and every topic of your own, that has
   stories: the mean of the stories filed in it or anywhere below it. */
export function nodeVectors(stories: Story[], own: Topic[]): Map<string, Float32Array> {
  const groups = new Map<string, Int8Array[]>();
  const add = (key: string, v: Int8Array) => { const g = groups.get(key); if (g) g.push(v); else groups.set(key, [v]); };
  for (const s of stories) {
    const v = decodeVector(s.centroid);
    if (!v) continue;
    for (const p of new Set(s.topics.flatMap(placesOf))) add(`n:${p}`, v);
    for (const t of own) if (fits(s, t)) add(`own:${t.id}`, v);
  }
  const out = new Map<string, Float32Array>();
  for (const [k, g] of groups) { const m = meanOf(g); if (m) out.set(k, m); }
  for (const t of own) {
    // A topic of your own with no stories yet still has its description.
    const tv = decodeVector(t.vector);
    if (!out.has(`own:${t.id}`) && tv) out.set(`own:${t.id}`, meanOf([tv])!);
  }
  return out;
}

/* Which pairs may be linked as related: topics at the same depth, and never a
   pair the tree already joins. Categories may relate to each other; deeper
   down, topics in the same place are siblings already, so only topics in
   different places are compared. Your own topics compare with anything. */
function comparable(a: GNode, b: GNode): boolean {
  if (a.key === b.key || a.kind === 'area' || b.kind === 'area' || a.kind === 'src' || b.kind === 'src') return false;
  if (a.kind === 'own' || b.kind === 'own') return true;
  if (a.depth !== b.depth) return false;
  return a.depth === 1 || a.parent !== b.parent;
}

/* The closest few to one node, best first. */
export function closest(node: GNode, nodes: GNode[], vectors: Map<string, Float32Array>, n: number) {
  const v = vectors.get(node.key);
  if (!v) return [];
  return nodes
    .filter((o) => comparable(node, o) && vectors.has(o.key))
    .map((o) => ({ node: o, score: cos(v, vectors.get(o.key)!) }))
    .sort((x, y) => y.score - x.score)
    .slice(0, n);
}

/* The links drawn when nothing is focused: each category, and each topic of
   your own, to its closest one. Deeper topics wait for a tap -- every one
   linked at once was a hairball. */
export function overviewEdges(nodes: GNode[], vectors: Map<string, Float32Array>): GEdge[] {
  const tops = nodes.filter((n) => (n.kind === 'branch' && n.depth === 1) || n.kind === 'own');
  const seen = new Map<string, GEdge>();
  for (const a of tops) {
    const best = closest(a, tops, vectors, 1)[0];
    if (!best) continue;
    const id = [a.key, best.node.key].sort().join('|');
    if (!seen.has(id)) seen.set(id, { a: a.key, b: best.node.key, kind: 'rel', strength: best.score });
  }
  return [...seen.values()];
}

/* A focused node's links: its closest few, wherever they sit. */
export function focusEdges(node: GNode, nodes: GNode[], vectors: Map<string, Float32Array>, n = 3): GEdge[] {
  return closest(node, nodes, vectors, n).map(({ node: b, score }) => ({ a: node.key, b: b.key, kind: 'rel' as const, strength: score }));
}

type Sim = GNode & SimulationNodeDatum & { tx?: number; ty?: number };

const RING = [0, 210, 370, 510, 640, 760]; // radius per depth

/* Lay the tree out as a radial tree first -- each category a wedge of the
   circle sized by what is in it, each depth on its own ring -- then let a
   light force pass push labels off each other and draw related topics a
   little closer. Forces alone put AI's forty topics on one side and the other
   categories in a heap on the other; the wedges keep News surrounded. The
   same input always gives the same picture. */
export function layout(nodes: GNode[], links: GEdge[]) {
  const sim = nodes as Sim[];
  const parent = new Map<string, string>();
  for (const e of links) if (e.kind === 'tree') parent.set(e.b, e.a);
  const kids = new Map<string, Sim[]>();
  for (const n of sim) { const p = parent.get(n.key); if (p && p !== 'area') kids.set(p, [...(kids.get(p) || []), n]); }
  const firsts = sim.filter((n) => n.kind === 'own' || (n.depth === 1 && n.kind !== 'src'));
  // Each branch gets room by how much is in it, damped: AI's forty topics
  // must not leave Sport's three squeezed against the hub.
  const size = new Map<string, number>();
  const count = (n: Sim): number => {
    if (!size.has(n.key)) size.set(n.key, 1 + (kids.get(n.key) || []).reduce((t, c) => t + count(c), 0));
    return size.get(n.key)!;
  };
  const weight = (n: Sim) => Math.sqrt(count(n));
  const ring = (d: number) => RING[Math.min(d, RING.length - 1)];
  const place = (n: Sim, from: number, span: number) => {
    const a = from + span / 2;
    n.tx = Math.cos(a) * ring(n.depth); n.ty = Math.sin(a) * ring(n.depth);
    const under = kids.get(n.key) || [];
    const total = under.reduce((t, c) => t + weight(c), 0) || 1;
    let at = from;
    for (const c of under) { const share = (span * weight(c)) / total; place(c, at, share); at += share; }
  };
  const total = firsts.reduce((t, n) => t + weight(n), 0) || 1;
  let from = -Math.PI / 2;
  for (const n of firsts) { const span = (Math.PI * 2 * weight(n)) / total; place(n, from, span); from += span; }
  // Sources sit outside everything, between the topics they feed.
  const deepest = Math.max(...sim.filter((n) => n.kind !== 'src').map((n) => n.depth), 1);
  for (const n of sim) {
    if (n.kind === 'area') { n.tx = 0; n.ty = 0; n.fx = 0; n.fy = 0; }
    if (n.kind !== 'src') continue;
    const fed = links.filter((e) => e.b === n.key).map((e) => sim.find((m) => m.key === e.a)).filter(Boolean) as Sim[];
    let sx = 0, sy = 0;
    for (const f of fed) { sx += f.tx ?? 0; sy += f.ty ?? 0; }
    const a = Math.atan2(sy, sx);
    n.tx = Math.cos(a) * (ring(deepest) + 150); n.ty = Math.sin(a) * (ring(deepest) + 150);
  }
  for (const n of sim) { n.x = n.tx ?? 0; n.y = n.ty ?? 0; }

  const byKey = new Map(sim.map((n) => [n.key, n]));
  const related = links.filter((e) => e.kind === 'rel' && byKey.has(e.a) && byKey.has(e.b))
    .map((e) => ({ source: byKey.get(e.a)!, target: byKey.get(e.b)! }));
  forceSimulation(sim)
    .force('x', forceX<Sim>((n) => n.tx ?? 0).strength(0.35))
    .force('y', forceY<Sim>((n) => n.ty ?? 0).strength(0.35))
    .force('related', forceLink<Sim, SimulationLinkDatum<Sim>>(related).distance(200).strength(0.02))
    // Labels are wide and short. Topics with others inside get their whole
    // half-width so their names never touch at full size; the rest tuck closer.
    .force('collide', forceCollide<Sim>((n) => (n.kind === 'leaf' || n.kind === 'src' ? n.w * 0.42 : n.w / 2) + 8).strength(0.9))
    .stop()
    .tick(220);
  for (const n of sim) { delete n.vx; delete n.vy; delete n.index; delete n.tx; delete n.ty; }
}

export function buildGraph(bundle: Bundle, profile: Profile, opts: Options) {
  const own = profile.topics.filter((t) => !t.spine);
  const followed = profile.topics.filter((t) => t.spine);
  const parentOf = new Map(bundle.spine.map((t) => [t.slug, t.parent ?? null]));
  const above = (slug: string) => {
    const out: string[] = [];
    let at = parentOf.get(slug);
    while (at && !out.includes(at)) { out.push(at); at = parentOf.get(at); }
    return out;
  };
  // The topic of yours a place opens in: the nearest followed one at or above it.
  const opensIn = (slug: string) => {
    for (const s of [slug, ...above(slug)]) { const t = followed.find((x) => x.spine === s); if (t) return t; }
    return undefined;
  };
  // "Yours" shows what you follow, everything inside it, and the way up to News.
  const shown = new Set<string>();
  if (opts.scope === 'all') for (const t of bundle.spine) shown.add(t.slug);
  else {
    for (const t of followed) {
      shown.add(t.spine!);
      for (const a of above(t.spine!)) shown.add(a);
      for (const n of bundle.spine) if (above(n.slug).includes(t.spine!)) shown.add(n.slug);
    }
  }
  const hasKids = new Set(bundle.spine.map((t) => t.parent).filter(Boolean) as string[]);

  const nodes: GNode[] = [];
  const edges: GEdge[] = [];
  if (shown.size) nodes.push({ key: 'area', kind: 'area', label: ROOT, x: 0, y: 0, ...sizeOf('area', 0, ROOT), depth: 0, followed: true });
  for (const t of bundle.spine) {
    if (!shown.has(t.slug)) continue;
    const ups = above(t.slug);
    const depth = ups.length + 1;
    const kind: Kind = hasKids.has(t.slug) ? 'branch' : 'leaf';
    const home = opensIn(t.slug);
    nodes.push({ key: `n:${t.slug}`, kind, label: t.name, x: 0, y: 0, ...sizeOf(kind, depth, t.name), depth,
      slug: t.slug, parent: t.parent ?? undefined, top: ups[ups.length - 1] ?? t.slug, topicId: home?.id, followed: !!home,
      mine: followed.some((x) => x.spine === t.slug) });
    edges.push({ a: t.parent ? `n:${t.parent}` : 'area', b: `n:${t.slug}`, kind: 'tree' });
  }
  for (const t of own) {
    nodes.push({ key: `own:${t.id}`, kind: 'own', label: t.name, x: 0, y: 0, ...sizeOf('own', 1, t.name), depth: 1,
      topicId: t.id, followed: true });
  }

  if (opts.sources) {
    // One node per source, joined to every topic it feeds: a source shared
    // by two topics is one of the ways they relate.
    for (const t of profile.topics) {
      const key = t.spine ? `n:${t.spine}` : `own:${t.id}`;
      if (!nodes.some((n) => n.key === key)) continue;
      for (const name of t.sources.slice(0, SOURCES_PER_TOPIC)) {
        const sk = `src:${name}`;
        if (!nodes.some((n) => n.key === sk)) nodes.push({ key: sk, kind: 'src', label: name, x: 0, y: 0, ...sizeOf('src', 9, name), depth: 9, followed: true });
        edges.push({ a: key, b: sk, kind: 'src' });
      }
    }
  }

  const vectors = nodeVectors(bundle.stories, own);
  // Related links shape the layout even when hidden, so turning them off and
  // on does not rearrange the picture.
  const rel = overviewEdges(nodes, vectors);
  layout(nodes, [...edges, ...rel]);
  return { nodes, edges, overview: opts.related ? rel : [], vectors, related: opts.related };
}

/* The dashed lines to draw: none with Related off, whether or not a topic is
   selected; a selected topic's closest few; otherwise each category's closest. */
export function relatedEdges(g: ReturnType<typeof buildGraph>, selected?: GNode): GEdge[] {
  if (!g.related) return [];
  return selected ? focusEdges(selected, g.nodes, g.vectors) : g.overview;
}
