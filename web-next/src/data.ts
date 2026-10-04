/* The bundle the pipeline publishes (`trib export` writes it as data.json),
   and what the new page derives from it. Version 1's JSON contract is kept as
   it is: everything here is read from the bundle, nothing is asked of a server. */

export interface Label { slug: string; name: string; parent?: string | null; parent_name?: string | null }
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
  shelves: Map<string, number>; // shelf slug -> stories it put there
}

export const HOUR = 3600e3;
export const NEW_HOURS = 48;

export async function loadBundle(): Promise<Bundle> {
  // Under /next/ on Pages the pipeline's bundle sits one level up; in local
  // development it is the generated sample (scripts/make_dev_data.py).
  const url = import.meta.env.DEV ? '/dev-data.json' : '../data.json';
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

/* The shelf a story lives on: its label's parent, or the label itself. */
export const shelfOf = (l: Label) => l.parent || l.slug;
export const storySources = (s: Story) => [...new Set([s.source, ...s.items.map((i) => i.source)])];

export function buildCatalog(bundle: Bundle): Map<string, Source> {
  const out = new Map<string, Source>();
  const get = (name: string) => {
    if (!out.has(name)) out.set(name, { name, week: 0, latest: [], shelves: new Map() });
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
        const shelf = shelfOf(label);
        src.shelves.set(shelf, (src.shelves.get(shelf) || 0) + 1);
      }
    }
  }
  return out;
}

/* The starter subjects: the spine's shelves, each with the leaves under it. */
export function shelves(bundle: Bundle) {
  const tops = bundle.spine.filter((t) => !t.parent);
  return tops.map((t) => ({ ...t, leaves: bundle.spine.filter((l) => l.parent === t.slug) }));
}

/* What the first run and "new topic" suggest for a shelf: the sources that
   put stories there, busiest first. On the backend this becomes real
   discovery; here it is only what the pipeline already reads. */
export function sourcesForShelf(catalog: Map<string, Source>, shelf: string): Source[] {
  return [...catalog.values()]
    .filter((s) => (s.shelves.get(shelf) || 0) > 0)
    .sort((a, b) => (b.shelves.get(shelf) || 0) - (a.shelves.get(shelf) || 0));
}

export const isBusy = (s: Source) => s.week >= 300;
