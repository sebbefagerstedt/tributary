/* The tree as an ontology graph: AI at the hub, its topics, their subtopics,
   your own topics, the sources feeding them -- and dashed links between
   topics that write about similar things. Laid out by forces (d3-force):
   every link pulls its ends together, every node pushes the others away, and
   a label's width keeps it off its neighbours, so related topics drift close
   and the picture settles into the shape of the subject.

   "Similar" is the stories' vectors: a topic's vector is the re-normalised
   mean of the centroids of the stories filed under it (the bundle carries
   them), so two topics are related when their stories point the same way.
   Each topic is linked to its closest few, ranked rather than cut at a
   threshold -- every cosine inside one subject is high, and a comparison
   needs no scale (CLAUDE.md, "Topics have no threshold"). Pure functions only,
   so the maths is testable without a browser. */

import { Bundle, STARTER_AREA, Story, shelfOf } from './data';
import { Profile, Topic, fits } from './state';
import { decodeVector } from './vectors';
import { SimulationLinkDatum, SimulationNodeDatum, forceCollide, forceLink, forceManyBody, forceSimulation } from 'd3-force';

export type Kind = 'area' | 'shelf' | 'leaf' | 'own' | 'src';
export interface GNode {
  key: string; kind: Kind; label: string;
  x: number; y: number; w: number; h: number; // centre, and size at zoom 1
  shelf?: string;      // a leaf's shelf, or the shelf itself
  slug?: string;       // spine slug for a shelf or a leaf
  topicId?: string;    // the reader's topic this opens, if any
  followed: boolean;   // in the reader's topics (a leaf: its shelf is)
}
export interface GEdge { a: string; b: string; kind: 'tree' | 'rel' | 'src'; strength?: number }
export interface Options { scope: 'mine' | 'all'; related: boolean; sources: boolean }

const FONT = { area: 0, shelf: 13, own: 13, leaf: 11.5, src: 11 } as const;
const HEIGHT = { area: 44, shelf: 30, own: 30, leaf: 24, src: 22 } as const;
const SOURCES_PER_TOPIC = 4;
export const labelWidth = (kind: Kind, label: string) =>
  kind === 'area' ? 44 : Math.min(label.length, 26) * FONT[kind] * 0.56 + (kind === 'leaf' ? 30 : 24);

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

/* A vector for every shelf, leaf and topic of your own that has stories. */
export function nodeVectors(stories: Story[], own: Topic[]): Map<string, Float32Array> {
  const groups = new Map<string, Int8Array[]>();
  const add = (key: string, v: Int8Array) => { const g = groups.get(key); if (g) g.push(v); else groups.set(key, [v]); };
  for (const s of stories) {
    const v = decodeVector(s.centroid);
    if (!v) continue;
    for (const l of s.topics) {
      if (l.parent) add(`leaf:${l.slug}`, v);
      add(`shelf:${shelfOf(l)}`, v);
    }
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

/* Which pairs may be linked as related: like with like, and never a pair the
   tree already joins (a leaf and its shelf, two leaves on one shelf). */
function comparable(a: GNode, b: GNode): boolean {
  if (a.key === b.key) return false;
  if (a.kind === 'own' || b.kind === 'own') return a.kind !== 'area' && b.kind !== 'area' && a.kind !== 'src' && b.kind !== 'src';
  if (a.kind === 'shelf' && b.kind === 'shelf') return true;
  if (a.kind === 'leaf' && b.kind === 'leaf') return a.shelf !== b.shelf;
  return false;
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

/* The links drawn when nothing is focused: each topic to its closest one.
   Subtopics wait for a tap -- every one linked at once was a hairball. */
export function overviewEdges(nodes: GNode[], vectors: Map<string, Float32Array>): GEdge[] {
  const tops = nodes.filter((n) => n.kind === 'shelf' || n.kind === 'own');
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

type Sim = GNode & SimulationNodeDatum;

/* Settle the graph: start from rings (hub, topics, subtopics, sources) so the
   forces only tidy, then run a fixed number of ticks -- the same input always
   gives the same picture. */
export function layout(nodes: GNode[], links: GEdge[]) {
  const sim = nodes as Sim[];
  const tops = sim.filter((n) => n.kind === 'shelf' || n.kind === 'own');
  const angle = new Map<string, number>();
  tops.forEach((n, i) => {
    const a = -Math.PI / 2 + (i / Math.max(tops.length, 1)) * Math.PI * 2;
    angle.set(n.key, a);
    n.x = Math.cos(a) * 200; n.y = Math.sin(a) * 200;
  });
  const parent = new Map<string, string>();
  for (const e of links) if (e.kind !== 'rel') parent.set(e.b, e.a);
  let k = 0;
  for (const n of sim) {
    if (n.kind === 'area') { n.x = 0; n.y = 0; n.fx = 0; n.fy = 0; continue; }
    if (angle.has(n.key)) continue;
    const a = (angle.get(parent.get(n.key) || '') ?? 0) + ((k++ % 7) - 3) * 0.09;
    const r = n.kind === 'src' ? 520 : 360;
    n.x = Math.cos(a) * r; n.y = Math.sin(a) * r;
  }
  const byKey = new Map(sim.map((n) => [n.key, n]));
  const simLinks: (SimulationLinkDatum<Sim> & { e: GEdge })[] = links
    .filter((e) => byKey.has(e.a) && byKey.has(e.b))
    .map((e) => ({ source: byKey.get(e.a)!, target: byKey.get(e.b)!, e }));
  forceSimulation(sim)
    .force('link', forceLink(simLinks)
      .distance((l) => ({ tree: (l.e.a === 'area' ? 190 : 110), src: 140, rel: 260 })[l.e.kind])
      .strength((l) => ({ tree: 0.7, src: 0.25, rel: 0.06 })[l.e.kind]))
    .force('charge', forceManyBody<Sim>().strength((n) => (n.kind === 'leaf' || n.kind === 'src' ? -140 : -380)))
    // Pills are wide and short. Topics get their whole half-width so their
    // names never touch at full size; smaller pills may tuck in closer.
    .force('collide', forceCollide<Sim>((n) => (n.kind === 'leaf' || n.kind === 'src' ? n.w * 0.42 : n.w / 2) + 8).strength(0.9))
    .stop()
    .tick(320);
  for (const n of sim) { delete n.vx; delete n.vy; delete n.index; }
}

export function buildGraph(bundle: Bundle, profile: Profile, opts: Options) {
  const own = profile.topics.filter((t) => !t.spine);
  const mine = new Map(profile.topics.filter((t) => t.spine).map((t) => [t.spine!, t]));
  const allShelves = bundle.spine.filter((l) => !l.parent);
  const shelves = opts.scope === 'all' ? allShelves : allShelves.filter((s) => mine.has(s.slug));

  const nodes: GNode[] = [];
  const edges: GEdge[] = [];
  const add = (n: Omit<GNode, 'x' | 'y' | 'w' | 'h'>, parentKey?: string) => {
    nodes.push({ ...n, x: 0, y: 0, w: labelWidth(n.kind, n.label), h: HEIGHT[n.kind] });
    if (parentKey) edges.push({ a: parentKey, b: n.key, kind: 'tree' });
  };
  if (shelves.length) add({ key: 'area', kind: 'area', label: STARTER_AREA, followed: true });
  for (const s of shelves) {
    const t = mine.get(s.slug);
    const key = `shelf:${s.slug}`;
    add({ key, kind: 'shelf', label: s.name, shelf: s.slug, slug: s.slug, topicId: t?.id, followed: !!t }, 'area');
    for (const l of bundle.spine.filter((x) => x.parent === s.slug)) {
      add({ key: `leaf:${l.slug}`, kind: 'leaf', label: l.name, shelf: s.slug, slug: l.slug, topicId: t?.id, followed: !!t }, key);
    }
  }
  for (const t of own) add({ key: `own:${t.id}`, kind: 'own', label: t.name, topicId: t.id, followed: true });

  if (opts.sources) {
    // One node per source, joined to every topic it feeds: a source shared
    // by two topics is one of the ways they relate.
    for (const t of profile.topics) {
      const key = t.spine ? `shelf:${t.spine}` : `own:${t.id}`;
      if (!nodes.some((n) => n.key === key)) continue;
      for (const name of t.sources.slice(0, SOURCES_PER_TOPIC)) {
        const sk = `src:${name}`;
        if (!nodes.some((n) => n.key === sk)) nodes.push({ key: sk, kind: 'src', label: name, x: 0, y: 0, w: labelWidth('src', name), h: HEIGHT.src, followed: true });
        edges.push({ a: key, b: sk, kind: 'src' });
      }
    }
  }

  const vectors = nodeVectors(bundle.stories, own);
  // Related links shape the layout even when hidden, so turning them off and
  // on does not rearrange the picture.
  const rel = overviewEdges(nodes, vectors);
  layout(nodes, [...edges, ...rel]);
  return { nodes, edges, overview: opts.related ? rel : [], vectors };
}
