/* The bundle the pipeline publishes (`trib export` writes it as data.json),
   and what the new page derives from it. Version 1's JSON contract is kept as
   it is: everything here is read from the bundle, nothing is asked of a server. */

export interface Label {
  slug: string; name: string; parent?: string | null; parent_name?: string | null;
  path?: string[];             // every topic above this one, the top first
  description?: string | null; // topics with others under them: what they hold
}
export interface Item {
  role: string; kind: string; title: string; url: string; author: string | null;
  source: string; published_at: string | null; summary: string | null;
}
export interface Story {
  story_id: number; title: string; summary: string | null; url: string; kind: string;
  source: string; sources: number; published_at: string | null; last_activity: string | null;
  item_count: number; media_url: string | null; centroid?: string | null; topics: Label[]; items: Item[];
}
export interface Bundle {
  generated_at: string;
  status: { broken_sources: { name: string; error: string }[] };
  spine: Label[];
  stories: Story[];
}

/* A source as the page knows it: everything in the bundle that names it. */
export interface Source {
  name: string;
  week: number;          // items in the last seven days
  latest: string[];      // its newest headlines, for the preview
  places: Map<string, number>; // topic slug -> stories it put there or below
}

export const HOUR = 3600e3;
export const NEW_HOURS = 48;

export async function loadBundle(): Promise<Bundle> {
  // Under /next/ on Pages the pipeline's bundle sits one level up; in local
  // development it is the generated sample (scripts/make_dev_data.py).
  const url = import.meta.env.DEV ? '/dev-data.json' : './data.json';
  const res = await fetch(url, { cache: 'no-store' });
  if (!res.ok) throw new Error(`Could not load the news (${res.status}).`);
  return res.json();
}

export const ageHours = (iso: string | null) =>
  iso ? (Date.now() - Date.parse(iso)) / HOUR : Infinity;

export const agoLabel = (iso: string | null) => {
  const h = ageHours(iso);
  if (!Number.isFinite(h)) return '';
  if (h < 1) return 'now';
  return h < 24 ? `${Math.floor(h)}h` : `${Math.floor(h / 24)}d`;
};

/* Every topic a label puts a story in: the one it was filed under and all
   those above it. A bundle from before the tree had depth has no `path`, and
   then the parent is all there is. */
export const placesOf = (l: Label) => [...(l.path ?? (l.parent ? [l.parent] : [])), l.slug];
export const inPlace = (story: Story, slug: string) => story.topics.some((l) => placesOf(l).includes(slug));
export const storySources = (s: Story) => [...new Set([s.source, ...s.items.map((i) => i.source)])];

export function buildCatalog(bundle: Bundle): Map<string, Source> {
  const out = new Map<string, Source>();
  const get = (name: string) => {
    if (!out.has(name)) out.set(name, { name, week: 0, latest: [], places: new Map() });
    return out.get(name)!;
  };
  const byDate = [...bundle.stories].sort((a, b) => ageHours(a.published_at) - ageHours(b.published_at));
  for (const story of byDate) {
    for (const item of story.items) {
      const src = get(item.source);
      if (ageHours(item.published_at || story.published_at) < 24 * 7) src.week += 1;
      if (src.latest.length < 3 && !src.latest.includes(item.title)) src.latest.push(item.title);
    }
    for (const name of storySources(story)) {
      const src = get(name);
      for (const label of story.topics) {
        for (const place of placesOf(label)) src.places.set(place, (src.places.get(place) || 0) + 1);
      }
    }
  }
  return out;
}

/* The hub of the tree. The topics are general news since 2026-10-05; AI is
   one branch, under Technology. */
export const ROOT = 'News';

/* The tree, read from the bundle's spine. */
export const childrenOf = (bundle: Bundle, slug: string | null) =>
  bundle.spine.filter((t) => (t.parent ?? null) === slug);
export const nodeOf = (bundle: Bundle, slug: string) => bundle.spine.find((t) => t.slug === slug);
/* The topics above one, the top first. */
export function pathTo(bundle: Bundle, slug: string): Label[] {
  const out: Label[] = [];
  let at = nodeOf(bundle, slug)?.parent;
  while (at && !out.some((l) => l.slug === at)) {
    const n = nodeOf(bundle, at);
    if (!n) break;
    out.unshift(n);
    at = n.parent;
  }
  return out;
}

/* The starter subjects: the categories at the top, each with what is under it. */
export function categories(bundle: Bundle) {
  return childrenOf(bundle, null).map((t) => ({ ...t, leaves: childrenOf(bundle, t.slug) }));
}

/* What the first run and "new topic" suggest for a topic: the sources that
   put stories in it or below it, busiest first. On the backend this becomes
   real discovery; here it is only what the pipeline already reads. */
export function sourcesFor(catalog: Map<string, Source>, slug: string): Source[] {
  return [...catalog.values()]
    .filter((s) => (s.places.get(slug) || 0) > 0)
    .sort((a, b) => (b.places.get(slug) || 0) - (a.places.get(slug) || 0));
}

export const isBusy = (s: Source) => s.week >= 300;
