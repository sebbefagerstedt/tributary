/* What belongs to a reader: their profile, topics, what they have seen, and how
   they like to look at things. On this device, in localStorage, until the
   backend exists — the same shape will move to the server unchanged. */

import { useCallback, useEffect, useState } from 'react';
import { Label, NEW_HOURS, Story, ageHours, shelfOf, storySources } from './data';

export interface Topic {
  id: string;          // the spine shelf it started from
  name: string;
  sources: string[];
  muted: string[];
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

/* Profiles are names, no password (VISION.md). One device can hold several. */
export function useProfiles() {
  const [names, setNames] = useState<string[]>(() => read('profiles', []));
  const [current, setCurrent] = useState<string | null>(() => read('current', null));
  const [profile, setProfile] = useState<Profile | null>(() =>
    current ? read(`p:${current}`, blankProfile(current)) : null);

  useEffect(() => { if (profile) write(`p:${profile.name}`, profile); }, [profile]);

  const choose = useCallback((name: string) => {
    const clean = name.trim().slice(0, 24);
    if (!clean) return;
    setNames((prev) => { const next = prev.includes(clean) ? prev : [...prev, clean]; write('profiles', next); return next; });
    write('current', clean);
    setCurrent(clean);
    setProfile(read(`p:${clean}`, blankProfile(clean)));
  }, []);

  const signOut = useCallback(() => { write('current', null); setCurrent(null); setProfile(null); }, []);

  const update = useCallback((fn: (p: Profile) => Profile) => setProfile((p) => (p ? fn(p) : p)), []);

  return { names, profile, choose, signOut, update };
}

/* A story is in a topic when it lives on the topic's shelf, came from one of
   the topic's sources, and mentions none of its muted words. */
export function inTopic(story: Story, topic: Topic, leaf?: string) {
  const here = story.topics.some((l: Label) => (leaf ? l.slug === leaf : shelfOf(l) === topic.id));
  if (!here) return false;
  if (!storySources(story).some((s) => topic.sources.includes(s))) return false;
  const text = `${story.title} ${story.summary || ''}`.toLowerCase();
  return !topic.muted.some((w) => text.includes(w.toLowerCase()));
}

export const isSeen = (p: Profile, s: Story) => p.seen.includes(s.story_id);
/* New is unread and under 48 hours old, as in version 1. */
export const isNew = (p: Profile, s: Story) => !isSeen(p, s) && ageHours(s.published_at) < NEW_HOURS;

export const byNewest = (a: Story, b: Story) => ageHours(a.published_at) - ageHours(b.published_at);
