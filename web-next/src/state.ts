/* What belongs to a reader: their profile, topics, what they have seen, and how
   they like to look at things. On the owner's computer it lives on the server
   (`trib serve`); on GitHub Pages it lives in this browser. The shape is the
   same either way (VISION.md: only where the row is stored changes). */

import { useCallback, useEffect, useRef, useState } from 'react';
import { NEW_HOURS, Story, ageHours, inPlace, storySources } from './data';
import { remote } from './remote';
import { cosine, decodeVector } from './vectors';

export interface SourceSpec { name: string; url: string; kind: string }
export interface Topic {
  id: string;
  name: string;
  sources: string[];
  muted: string[];
  description?: string | null;
  spine?: string | null;   // the topic in the shared tree it borrows placements from
  parent?: string | null;
  vector?: string | null;  // its description embedded, for topics the spine does not know
  examples?: number[];     // stories it was taught by: following one event starts from its story
  found?: Record<string, SourceSpec>; // sources found on the web, not yet saved
}
export interface Profile {
  name: string;
  onboarded: boolean;
  topics: Topic[];
  seen: number[];
  layout: 'grid' | 'cards';
}

const KEY = 'trib-next:';
const read = <T,>(k: string, d: T): T => {
  try { const v = localStorage.getItem(KEY + k); return v === null ? d : JSON.parse(v); } catch { return d; }
};
const write = (k: string, v: unknown) => {
  try { localStorage.setItem(KEY + k, JSON.stringify(v)); } catch { /* storage off: works for this visit */ }
};

export const blankProfile = (name: string): Profile =>
  ({ name, onboarded: false, topics: [], seen: [], layout: 'grid' });

/* Topics saved in this browser before step 2 all started from a starter
   subject and carried no `spine`; their id was the shelf. */
const normalise = (p: Profile): Profile =>
  ({ ...p, topics: p.topics.map((t) => (t.spine === undefined ? { ...t, spine: t.id } : t)) });

/* A topic as saved, without what only the server computes or the page holds
   briefly — to tell whether it changed. */
const topicKey = (t: Topic) => JSON.stringify([t.name, t.description, t.spine, t.parent, t.muted, t.sources, t.examples]);

/* Profiles are names, no password (VISION.md). One device can hold several;
   with a server, every device sees the same ones. */
export function useProfiles(server: boolean | null, onError: (msg: string) => void, onNewSources: () => void) {
  const [names, setNames] = useState<string[]>(() => read('profiles', []));
  const [current, setCurrent] = useState<string | null>(() => read('current', null));
  const [profile, setProfile] = useState<Profile | null>(null);
  const ref = useRef<Profile | null>(null);
  const set = (p: Profile | null) => { ref.current = p; setProfile(p); };

  useEffect(() => {
    if (server === null) return;
    if (server) {
      remote.profiles().then(setNames).catch((e) => onError(e.message));
      if (current) remote.profile(current).then(set).catch(() => { write('current', null); setCurrent(null); });
    } else if (current) {
      set(normalise(read(`p:${current}`, blankProfile(current))));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [server]);

  useEffect(() => { if (server === false && profile) write(`p:${profile.name}`, profile); }, [server, profile]);

  const choose = useCallback(async (name: string) => {
    const clean = name.trim().slice(0, 24);
    if (!clean) return;
    write('current', clean);
    setCurrent(clean);
    if (server) {
      try {
        set(await remote.create(clean));
        setNames((n) => (n.includes(clean) ? n : [...n, clean]));
      } catch (e) { onError((e as Error).message); }
      return;
    }
    setNames((prev) => { const next = prev.includes(clean) ? prev : [...prev, clean]; write('profiles', next); return next; });
    set(normalise(read(`p:${clean}`, blankProfile(clean))));
  }, [server, onError]);

  const signOut = useCallback(() => { write('current', null); setCurrent(null); set(null); }, []);

  /* Change the profile here at once, then tell the server what changed. */
  const update = useCallback((fn: (p: Profile) => Profile) => {
    const prev = ref.current;
    if (!prev) return;
    const next = fn(prev);
    set(next);
    if (!server) return;
    const name = next.name;
    const fail = (e: Error) => onError(`Could not save: ${e.message}`);
    if (prev.layout !== next.layout || prev.onboarded !== next.onboarded) {
      remote.patch(name, { layout: next.layout, onboarded: next.onboarded }).catch(fail);
    }
    const added = next.seen.filter((id) => !prev.seen.includes(id));
    if (added.length) remote.seen(name, added).catch(fail);
    for (const t of prev.topics) {
      if (!next.topics.some((x) => x.id === t.id)) remote.deleteTopic(name, t.id).catch(fail);
    }
    for (const t of next.topics) {
      const old = prev.topics.find((x) => x.id === t.id);
      if (old && topicKey(old) === topicKey(t)) continue;
      const fresh = t.sources.some((s) => t.found?.[s]);
      remote.saveTopic(name, t).then((saved) => {
        // Keep what only the server knows: the embedded description.
        const cur = ref.current;
        if (cur) set({ ...cur, topics: cur.topics.map((x) => (x.id === saved.id ? { ...x, vector: saved.vector, found: undefined } : x)) });
        if (fresh) onNewSources();
      }).catch(fail);
    }
  }, [server, onError, onNewSources]);

  const reset = useCallback(async () => {
    const prev = ref.current;
    if (!prev) return;
    if (server) {
      try { set(await remote.reset(prev.name)); } catch (e) { onError((e as Error).message); }
    } else {
      set({ ...blankProfile(prev.name), layout: prev.layout });
    }
  }, [server, onError]);

  return { names, profile, choose, signOut, update, reset };
}

/* Unmeasured, like the backend's suggest.FIT_FLOOR: the same number, so a
   suggestion and the topic it becomes agree about what fits. */
export const FIT_FLOOR = 0.62;

/* The words a topic's name asks for. Any letters, so "Göteborg" and "Ukraina"
   count; two letters is enough for AI, EU or F1, and the little words that
   say nothing about a subject are left out. */
const STOP = new Set(['the', 'and', 'of', 'in', 'on', 'to', 'for', 'an', 'a', 'at', 'by', 'or', 'news',
  'och', 'i', 'på', 'av', 'om', 'en', 'ett', 'med', 'för']);
export const words = (s: string) =>
  s.toLowerCase().split(/[^\p{L}\p{N}]+/u).filter((w) => w.length >= 2 && !STOP.has(w));
const escape = (w: string) => w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
/* A whole word, or its plural: "war" is not in "software", "agent" is in
   "agents". */
const mentions = (text: string, w: string) =>
  new RegExp(`(?<![\\p{L}\\p{N}])${escape(w)}(s|es)?(?![\\p{L}\\p{N}])`, 'u').test(text);

/* Every word of a name, each somewhere in the story. */
export function namedIn(story: Story, name: string): boolean {
  const asked = words(name);
  if (!asked.length) return false;
  const text = `${story.title} ${story.summary || ''} ${story.items.map((i) => i.title).join(' ')}`.toLowerCase();
  return asked.every((w) => mentions(text, w));
}

/* Does a story fit a topic? A topic from the shared tree borrows the
   pipeline's placement — the story was filed there or somewhere below it. A topic of your own
   asks words first (every word of its name in the story), then the vector, the
   order version 1's lenses used. Made without a server, it has no vector --
   nothing in the browser can embed a description -- and its words are all. This is the fit filter VISION.md keeps. */
export function fits(story: Story, topic: Topic, leaf?: string): boolean {
  if (topic.examples?.length) return likeExamples(story, topic);
  if (topic.spine) return inPlace(story, leaf || topic.spine);
  if (namedIn(story, topic.name)) return true;
  const tv = decodeVector(topic.vector), sv = decodeVector(story.centroid);
  return !!tv && !!sv && cosine(tv, sv) >= FIT_FLOOR;
}

/* How close a story must be to the one a topic was taught by. Far stricter
   than FIT_FLOOR: an event's topic wants that event and its follow-ups, not
   its whole subject -- at 0.62 "OpenAI rogue agents on Wikimedia" would have
   taken every AI-security story. Unmeasured (2026-10-07); the page shows what
   it would catch before you follow, so a wrong bar is visible at once. */
export const EVENT_FLOOR = 0.82;

/* A topic taught by stories holds them, and whatever comes close to them.
   Its words are not asked: a name you gave an event ("Rogue agents") is a
   label, not a query. */
export function likeExamples(story: Story, topic: Topic): boolean {
  if (topic.examples?.includes(story.story_id)) return true;
  const tv = decodeVector(topic.vector), sv = decodeVector(story.centroid);
  return !!tv && !!sv && cosine(tv, sv) >= EVENT_FLOOR;
}

/* A topic that follows one story: taught by it, fed by every source, since
   the follow-ups to an event come from anywhere. */
export function eventTopic(story: Story, name: string, sources: string[], id: string): Topic {
  return { id, name, description: story.title, spine: null, sources, muted: [],
    examples: [story.story_id], vector: story.centroid ?? null };
}

/* A short name to start from: the headline up to its first colon or dash,
   at most six words. You can change it before following. */
export function shortName(title: string): string {
  const head = title.split(/:\s| [–—-] /)[0];
  const words = head.split(/\s+/).filter(Boolean);
  return words.slice(0, 6).join(' ');
}

/* Two topics cannot share an id, so a name already taken gets a number. */
export function freeId(profile: Profile, base: string): string {
  let id = base, n = 2;
  while (profile.topics.some((t) => t.id === id)) id = `${base}-${n++}`;
  return id;
}

/* A story is in a topic when it fits it, came from one of the topic's sources,
   and mentions none of its muted words. */
export function inTopic(story: Story, topic: Topic, leaf?: string) {
  if (!fits(story, topic, leaf)) return false;
  if (!storySources(story).some((s) => topic.sources.includes(s))) return false;
  const text = `${story.title} ${story.summary || ''}`.toLowerCase();
  return !topic.muted.some((w) => text.includes(w.toLowerCase()));
}

/* Who follows the place a page stands on. `own` is a topic you follow that is
   this place itself -- it has the settings. `via` is a topic you follow that
   this place sits inside, when you have not followed the place on its own. A
   subtopic can be followed without its topic, and a topic without any of its
   subtopics: each is its own row in your topics. */
export function following(profile: Profile, topic: Topic, leaf?: string): { own?: Topic; via?: Topic } {
  const here = leaf || topic.spine;
  const followed = profile.topics.some((t) => t.id === topic.id);
  if (!here) return followed ? { own: topic } : {};
  const own = profile.topics.find((t) => t.spine === here) ?? (followed && !leaf ? topic : undefined);
  if (own) return { own };
  return followed ? { via: topic } : {};
}

/* A place in the shared tree as a topic you have not followed: everything the
   pipeline files there, from every source that files anything there. */
export const placeTopic = (slug: string, name: string, sources: string[]): Topic =>
  ({ id: slug, name, spine: slug, sources, muted: [] });

export const isSeen = (p: Profile, s: Story) => p.seen.includes(s.story_id);
/* New is unread and under 48 hours old, as in version 1. */
export const isNew = (p: Profile, s: Story) => !isSeen(p, s) && ageHours(s.published_at) < NEW_HOURS;

export const byNewest = (a: Story, b: Story) => ageHours(a.published_at) - ageHours(b.published_at);
