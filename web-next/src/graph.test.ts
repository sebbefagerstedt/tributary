import { describe, expect, it } from 'vitest';
import { Bundle, Story } from './data';
import { barsOf, buildGraph, closest, focusEdges, relatedEdges } from './graph';
import { blankProfile } from './state';

/* Unit vectors packed as the backend packs them: int8 at scale 127, base64. */
const pack = (...xs: number[]) => {
  const v = new Array(8).fill(0);
  xs.forEach((x, i) => { v[i] = x; });
  const n = Math.hypot(...v) || 1;
  return btoa(String.fromCharCode(...v.map((x) => (Math.round((x / n) * 127) + 256) % 256)));
};

let id = 0;
const story = (leaf: string, parent: string, centroid: string): Story => ({
  story_id: ++id, title: `s${id}`, summary: null, url: '', kind: 'article', source: 'Feed', sources: 1,
  published_at: new Date().toISOString(), last_activity: new Date().toISOString(), item_count: 1,
  media_url: null, centroid, topics: [{ slug: leaf, name: leaf, parent }], items: [],
});

// Three shelves. Chips' "accelerators" writes like Models' "open weights";
// Safety writes like neither.
const bundle: Bundle = {
  generated_at: '', status: { broken_sources: [] },
  spine: [
    { slug: 'models', name: 'Models' }, { slug: 'open', name: 'Open weights', parent: 'models' },
    { slug: 'frontier', name: 'Frontier', parent: 'models' },
    { slug: 'chips', name: 'Chips' }, { slug: 'accel', name: 'Accelerators', parent: 'chips' },
    { slug: 'safety', name: 'Safety' }, { slug: 'jail', name: 'Jailbreaks', parent: 'safety' },
  ],
  stories: [
    story('open', 'models', pack(1, 0.1)), story('frontier', 'models', pack(1, 0, 0.6)),
    story('accel', 'chips', pack(0.9, 0.3)), story('jail', 'safety', pack(0, 0, 0, 1)),
  ],
};

describe('the tree', () => {
  const me = { ...blankProfile('S'), topics: [{ id: 'models', name: 'Models', spine: 'models', sources: ['Feed'], muted: [] }] };

  it('puts News in the middle and joins its categories to it, not to the reader', () => {
    const g = buildGraph(bundle, me, { scope: 'all', related: false, sources: false });
    expect(g.nodes.find((n) => n.kind === 'area')!.label).toBe('News');
    expect(g.edges.filter((e) => e.a === 'area').map((e) => e.b).sort()).toEqual(['n:chips', 'n:models', 'n:safety']);
  });

  it('shows only your topics and their subtopics unless asked for everything', () => {
    const g = buildGraph(bundle, me, { scope: 'mine', related: false, sources: false });
    expect(g.nodes.map((n) => n.key).sort()).toEqual(['area', 'n:frontier', 'n:models', 'n:open']);
  });

  it('settles the same way every time, with News at the hub and subtopics beside their topic', () => {
    const one = buildGraph(bundle, me, { scope: 'all', related: false, sources: false });
    const two = buildGraph(bundle, me, { scope: 'all', related: false, sources: false });
    expect(one.nodes.map((n) => [n.x, n.y])).toEqual(two.nodes.map((n) => [n.x, n.y]));
    const at = (k: string) => one.nodes.find((n) => n.key === k)!;
    expect([at('area').x, at('area').y]).toEqual([0, 0]);
    const d = (a: string, b: string) => Math.hypot(at(a).x - at(b).x, at(a).y - at(b).y);
    expect(d('n:open', 'n:models')).toBeLessThan(d('n:open', 'n:safety'));
    expect(at('n:models').followed && !at('n:chips').followed).toBe(true);
  });

  it('relates subtopics on different topics by their stories, closest first', () => {
    const g = buildGraph(bundle, me, { scope: 'all', related: true, sources: false });
    const open = g.nodes.find((n) => n.key === 'n:open')!;
    const near = closest(open, g.nodes, g.vectors, 3).map((x) => x.node.key);
    expect(near[0]).toBe('n:accel');
    // Its sibling is joined by the tree already, so it is never "related".
    expect(near).not.toContain('n:frontier');
  });

  it('links each topic to its closest at rest, and a focused node to its closest few', () => {
    const g = buildGraph(bundle, me, { scope: 'all', related: true, sources: false });
    const pairs = g.overview.map((e) => [e.a, e.b].sort().join(' '));
    expect(pairs).toContain('n:chips n:models');
    expect(g.overview.every((e) => e.a.startsWith('n:') && e.b.startsWith('n:'))).toBe(true);
    const open = g.nodes.find((n) => n.key === 'n:open')!;
    expect(focusEdges(open, g.nodes, g.vectors, 1).map((e) => e.b)).toEqual(['n:accel']);
    expect(buildGraph(bundle, me, { scope: 'all', related: false, sources: false }).overview).toEqual([]);
  });

  it('draws a source once, joined to every topic it feeds', () => {
    const two = { ...me, topics: [...me.topics, { id: 'chips', name: 'Chips', spine: 'chips', sources: ['Feed'], muted: [] }] };
    const g = buildGraph(bundle, two, { scope: 'mine', related: false, sources: true });
    expect(g.nodes.filter((n) => n.kind === 'src').map((n) => n.key)).toEqual(['src:Feed']);
    expect(g.edges.filter((e) => e.kind === 'src').map((e) => e.a).sort()).toEqual(['n:chips', 'n:models']);
  });

  it('draws no related lines with Related off, even for a selected topic', () => {
    const on = buildGraph(bundle, me, { scope: 'all', related: true, sources: false });
    const off = buildGraph(bundle, me, { scope: 'all', related: false, sources: false });
    const open = (g: typeof on) => g.nodes.find((n) => n.key === 'n:open')!;
    expect(relatedEdges(on, open(on)).length).toBeGreaterThan(0);
    expect(relatedEdges(off, open(off))).toEqual([]);
    expect(relatedEdges(off)).toEqual([]);
  });

  it('links only what stands out, so a topic equally near everything gets no line', () => {
    const flat: Bundle = { ...bundle, stories: [
      story('open', 'models', pack(1, 0, 0, 0)), story('accel', 'chips', pack(0, 1, 0, 0)),
      story('jail', 'safety', pack(0, 0, 1, 0)), story('frontier', 'models', pack(0, 0, 0, 1)),
    ] };
    const g = buildGraph(flat, me, { scope: 'all', related: true, sources: false });
    const open = g.nodes.find((n) => n.key === 'n:open')!;
    expect(closest(open, g.nodes, g.vectors, 3)).toEqual([]);
  });

  it('shows how close a link is in one to three bars', () => {
    expect([barsOf(1), barsOf(1.6), barsOf(2.4)]).toEqual([1, 2, 3]);
  });
});
