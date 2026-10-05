import { describe, expect, it } from 'vitest';
import { Bundle, Story } from './data';
import { buildGraph, closest, focusEdges } from './graph';
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

  it('puts AI in the middle and joins its topics to it, not to the reader', () => {
    const g = buildGraph(bundle, me, { scope: 'all', related: false, sources: false });
    expect(g.nodes.find((n) => n.kind === 'area')!.label).toBe('AI');
    expect(g.edges.filter((e) => e.a === 'area').map((e) => e.b).sort()).toEqual(['shelf:chips', 'shelf:models', 'shelf:safety']);
  });

  it('shows only your topics and their subtopics unless asked for all of AI', () => {
    const g = buildGraph(bundle, me, { scope: 'mine', related: false, sources: false });
    expect(g.nodes.map((n) => n.key).sort()).toEqual(['area', 'leaf:frontier', 'leaf:open', 'shelf:models']);
  });

  it('reads as an outline: each subtopic below its topic, nothing on top of anything', () => {
    const g = buildGraph(bundle, me, { scope: 'all', related: false, sources: false });
    const ys = g.nodes.map((n) => n.y);
    expect(ys).toEqual([...ys].sort((a, b) => a - b));
    const at = (k: string) => g.nodes.find((n) => n.key === k)!;
    expect(at('leaf:open').y).toBeGreaterThan(at('shelf:models').y);
    expect(at('leaf:open').x).toBeGreaterThan(at('shelf:models').x);
    expect(at('shelf:models').followed && !at('shelf:chips').followed).toBe(true);
  });

  it('relates subtopics on different topics by their stories, closest first', () => {
    const g = buildGraph(bundle, me, { scope: 'all', related: true, sources: false });
    const open = g.nodes.find((n) => n.key === 'leaf:open')!;
    const near = closest(open, g.nodes, g.vectors, 3).map((x) => x.node.key);
    expect(near[0]).toBe('leaf:accel');
    // Its sibling is joined by the tree already, so it is never "related".
    expect(near).not.toContain('leaf:frontier');
  });

  it('links each topic to its closest at rest, and a focused node to its closest few', () => {
    const g = buildGraph(bundle, me, { scope: 'all', related: true, sources: false });
    const pairs = g.overview.map((e) => [e.a, e.b].sort().join(' '));
    expect(pairs).toContain('shelf:chips shelf:models');
    expect(g.overview.every((e) => e.a.startsWith('shelf:') && e.b.startsWith('shelf:'))).toBe(true);
    const open = g.nodes.find((n) => n.key === 'leaf:open')!;
    expect(focusEdges(open, g.nodes, g.vectors, 1).map((e) => e.b)).toEqual(['leaf:accel']);
    expect(buildGraph(bundle, me, { scope: 'all', related: false, sources: false }).overview).toEqual([]);
  });

  it('lists each topic\'s sources under it when asked', () => {
    const two = { ...me, topics: [...me.topics, { id: 'chips', name: 'Chips', spine: 'chips', sources: ['Feed'], muted: [] }] };
    const g = buildGraph(bundle, two, { scope: 'mine', related: false, sources: true });
    expect(g.edges.filter((e) => e.kind === 'src').map((e) => e.a).sort()).toEqual(['shelf:chips', 'shelf:models']);
  });
});
