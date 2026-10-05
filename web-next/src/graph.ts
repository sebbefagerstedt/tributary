/* The tree as a graph: AI in the middle, its topics around it, their
   subtopics outside them, your own topics beside the AI ones -- and dashed
   links between topics that write about similar things.

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

export type Kind = 'area' | 'shelf' | 'leaf' | 'own' | 'src';
export interface GNode {
  key: string; kind: Kind; label: string;
  x: number; y: number; w: number; h: number; // left edge, centre line, size
  shelf?: string;      // a leaf's shelf, or the shelf itself
  slug?: string;       // spine slug for a shelf or a leaf
  topicId?: string;    // the reader's topic this opens, if any
  parentKey?: string;  // what the tree joins it to
  followed: boolean;   // in the reader's topics (a leaf: its shelf is)
}
export interface GEdge { a: string; b: string; kind: 'tree' | 'rel' | 'src'; strength?: number }
export interface Options { scope: 'mine' | 'all'; related: boolean; sources: boolean }

/* An outline you scroll down rather than a wheel you pan around: on a phone a
   radial graph of fifty named nodes was three screens wide and its labels sat
   on each other (2026-10-05). Each row is one node, indented by depth. */
const ROW = { area: 46, shelf: 40, own: 40, leaf: 32, src: 30 } as const;
const INDENT = { area: 12, shelf: 40, own: 40, leaf: 74, src: 74 } as const;
const FONT = { area: 0, shelf: 13, own: 13, leaf: 11.5, src: 11 } as const;
const GROUP_GAP = 8;
const SOURCES_PER_TOPIC = 3;
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

export function buildGraph(bundle: Bundle, profile: Profile, opts: Options) {
  const own = profile.topics.filter((t) => !t.spine);
  const mine = new Map(profile.topics.filter((t) => t.spine).map((t) => [t.spine!, t]));
  const allShelves = bundle.spine.filter((l) => !l.parent);
  const shelves = opts.scope === 'all' ? allShelves : allShelves.filter((s) => mine.has(s.slug));

  const nodes: GNode[] = [];
  const edges: GEdge[] = [];
  let y = 0;
  const row = (n: Omit<GNode, 'y' | 'x' | 'w' | 'h'>) => {
    const h = ROW[n.kind];
    const node: GNode = { ...n, x: INDENT[n.kind], y: y + h / 2, w: labelWidth(n.kind, n.label), h };
    y += h;
    nodes.push(node);
    if (n.parentKey) edges.push({ a: n.parentKey, b: n.key, kind: n.kind === 'src' ? 'src' : 'tree' });
    return node;
  };
  const sourcesOf = (topicId: string | undefined, parentKey: string) => {
    if (!opts.sources || !topicId) return;
    const t = profile.topics.find((x) => x.id === topicId)!;
    for (const s of t.sources.slice(0, SOURCES_PER_TOPIC)) {
      row({ key: `src:${parentKey}:${s}`, kind: 'src', label: s, parentKey, followed: true });
    }
    if (t.sources.length > SOURCES_PER_TOPIC) {
      row({ key: `src:${parentKey}:more`, kind: 'src', label: `+${t.sources.length - SOURCES_PER_TOPIC} more`, parentKey, followed: true });
    }
  };

  if (shelves.length) row({ key: 'area', kind: 'area', label: STARTER_AREA, followed: true });
  for (const s of shelves) {
    y += GROUP_GAP;
    const t = mine.get(s.slug);
    const key = `shelf:${s.slug}`;
    row({ key, kind: 'shelf', label: s.name, shelf: s.slug, slug: s.slug, topicId: t?.id, parentKey: 'area', followed: !!t });
    for (const l of bundle.spine.filter((x) => x.parent === s.slug)) {
      row({ key: `leaf:${l.slug}`, kind: 'leaf', label: l.name, shelf: s.slug, slug: l.slug, topicId: t?.id, parentKey: key, followed: !!t });
    }
    sourcesOf(t?.id, key);
  }
  for (const t of own) {
    y += GROUP_GAP * 2;
    const key = `own:${t.id}`;
    row({ key, kind: 'own', label: t.name, topicId: t.id, followed: true });
    sourcesOf(t.id, key);
  }

  const vectors = nodeVectors(bundle.stories, own);
  const overview = opts.related ? overviewEdges(nodes, vectors) : [];
  return { nodes, edges, overview, vectors, height: y + 16 };
}
