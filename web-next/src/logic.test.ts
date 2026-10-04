import { describe, expect, it } from 'vitest';
import { Bundle, Story, buildCatalog, isGeneral, shelves, sourcesForShelf } from './data';
import { Topic, blankProfile, inTopic, isNew } from './state';

const hoursAgo = (h: number) => new Date(Date.now() - h * 3600e3).toISOString();
const story = (id: number, over: Partial<Story> = {}): Story => ({
  story_id: id, title: `Story ${id}`, summary: null, url: `https://e.test/${id}`, kind: 'article',
  source: 'Lab Blog', sources: 1, published_at: hoursAgo(3), last_activity: hoursAgo(3), item_count: 1,
  media_url: null, topics: [{ slug: 'agents-coding', name: 'Coding agents', parent: 'agents', parent_name: 'AI agents' }],
  items: [{ role: 'seed', kind: 'article', title: `Story ${id}`, url: `https://e.test/${id}`, author: null, source: 'Lab Blog', published_at: hoursAgo(3), summary: null }],
  ...over,
});
const topic: Topic = { id: 'agents', name: 'AI agents', sources: ['Lab Blog'], muted: [] };

describe('what reaches a topic', () => {
  it('takes a story on its shelf from one of its sources', () => {
    expect(inTopic(story(1), topic)).toBe(true);
  });
  it('leaves out a story from a source the topic does not use', () => {
    const s = story(2, { source: 'Other', items: [{ ...story(2).items[0], source: 'Other' }] });
    expect(inTopic(s, topic)).toBe(false);
  });
  it('counts a source that only joined the story later', () => {
    const s = story(3, { source: 'Other', items: [{ ...story(3).items[0], source: 'Other' }, { ...story(3).items[0], source: 'Lab Blog' }] });
    expect(inTopic(s, topic)).toBe(true);
  });
  it('leaves out a story on another shelf', () => {
    expect(inTopic(story(4, { topics: [{ slug: 'chips', name: 'Chips' }] }), topic)).toBe(false);
  });
  it('hides a story that mentions a muted word', () => {
    expect(inTopic(story(5, { title: 'Crypto agents are back' }), { ...topic, muted: ['crypto'] })).toBe(false);
  });
  it('narrows to one subtopic', () => {
    expect(inTopic(story(6), topic, 'agents-coding')).toBe(true);
    expect(inTopic(story(6), topic, 'agents-browser')).toBe(false);
  });
});

describe('new', () => {
  it('is unread and under 48 hours old', () => {
    const p = blankProfile('S');
    expect(isNew(p, story(1))).toBe(true);
    expect(isNew(p, story(2, { published_at: hoursAgo(72) }))).toBe(false);
    expect(isNew({ ...p, seen: [1] }, story(1))).toBe(false);
  });
});

describe('the source catalogue', () => {
  const bundle: Bundle = {
    generated_at: hoursAgo(0), status: { broken_sources: [] },
    spine: [{ slug: 'agents', name: 'AI agents' }, { slug: 'agents-coding', name: 'Coding agents', parent: 'agents' }, { slug: 'chips', name: 'Chips' }],
    stories: [story(1), story(2), story(3, { source: 'Wire', topics: [{ slug: 'chips', name: 'Chips' }],
      items: [{ ...story(3).items[0], source: 'Wire' }] })],
  };
  const catalog = buildCatalog(bundle);
  it('counts what each source published this week, with its newest headlines', () => {
    expect(catalog.get('Lab Blog')!.week).toBe(2);
    expect(catalog.get('Lab Blog')!.latest.length).toBe(2);
  });
  it('suggests for a shelf only the sources that put stories there', () => {
    expect(sourcesForShelf(catalog, 'agents').map((s) => s.name)).toEqual(['Lab Blog']);
    expect(sourcesForShelf(catalog, 'chips').map((s) => s.name)).toEqual(['Wire']);
  });
  it('offers the spine shelves as starter subjects, each with its leaves', () => {
    expect(shelves(bundle).map((s) => [s.slug, s.leaves.length])).toEqual([['agents', 1], ['chips', 0]]);
  });
  it('calls a source on five shelves general', () => {
    expect(isGeneral({ name: 'x', week: 1, latest: [], shelves: new Map([['a', 1], ['b', 1], ['c', 1], ['d', 1], ['e', 1]]) })).toBe(true);
  });
});
