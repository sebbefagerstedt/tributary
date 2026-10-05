/* The backend on the owner's computer (`trib serve`, NEXT.md step 2). When the
   page is served from there it keeps profiles and topics on the server and can
   discover sources on the open web; on GitHub Pages none of this answers and
   the page keeps everything in the browser, as before. */

import type { Profile, Topic } from './state';

/* Relative to the page: at the root of trib serve that is /api/next/; on
   GitHub Pages it is a path nothing answers, which is how the page knows. */
const base = () => new URL('./api/next/', window.location.href).toString();

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(base() + path, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  });
  if (!res.ok) {
    let detail = `${res.status}`;
    try { detail = (await res.json()).detail || detail; } catch { /* not JSON */ }
    throw new Error(detail);
  }
  return res.json();
}

export async function hasServer(): Promise<boolean> {
  try {
    const res = await fetch(base() + 'ping', { cache: 'no-store' });
    return res.ok && (await res.json()).ok === true;
  } catch {
    return false;
  }
}

export interface Candidate {
  name: string; url: string | null; kind: string; known: boolean;
  week: number; latest: string[]; fit?: number;
}
export interface Discovery { kind: 'site' | 'subject'; sources: Candidate[]; note: string }

const enc = encodeURIComponent;

export const remote = {
  profiles: () => call<{ profiles: string[] }>('profiles').then((r) => r.profiles),
  create: (name: string) => call<Profile>('profiles', { method: 'POST', body: JSON.stringify({ name }) }),
  profile: (name: string) => call<Profile>(`profiles/${enc(name)}`),
  patch: (name: string, body: Partial<Pick<Profile, 'layout' | 'onboarded'>>) =>
    call<Profile>(`profiles/${enc(name)}`, { method: 'PATCH', body: JSON.stringify(body) }),
  reset: (name: string) => call<Profile>(`profiles/${enc(name)}/reset`, { method: 'POST' }),
  saveTopic: (name: string, topic: Topic) => call<Topic>(`profiles/${enc(name)}/topics/${enc(topic.id)}`, {
    method: 'PUT',
    body: JSON.stringify({
      name: topic.name, description: topic.description, spine: topic.spine, parent: topic.parent,
      muted: topic.muted,
      // A source found on the web is sent whole, so the server can add it.
      sources: topic.sources.map((s) => topic.found?.[s] || s),
    }),
  }),
  deleteTopic: (name: string, id: string) =>
    call<{ ok: boolean }>(`profiles/${enc(name)}/topics/${enc(id)}`, { method: 'DELETE' }),
  seen: (name: string, ids: number[]) =>
    call<{ ok: boolean }>(`profiles/${enc(name)}/seen`, { method: 'POST', body: JSON.stringify({ story_ids: ids }) }),
  discover: (q: string) => call<Discovery>(`discover?q=${enc(q)}`),
  refresh: () => call<{ running: boolean; finished_at: string | null; ok: boolean | null }>('refresh', { method: 'POST' }),
  refreshStatus: () => call<{ running: boolean; finished_at: string | null; ok: boolean | null }>('refresh'),
};
