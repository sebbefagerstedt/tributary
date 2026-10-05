/* Sheets slide over the screen you are on: a topic's settings, a new topic,
   your profile, and a story. Each is one level of "back". */

import { FormEvent, ReactNode, useMemo, useRef, useState } from 'react';
import { Bundle, STARTER_AREA, Source, Story, agoLabel, isBusy, shelves, sourcesForShelf } from './data';
import { useDragToClose } from './gestures';
import { DiscoveredCard, asSource, slugOf, specsOf, useDiscovery } from './Discovery';
import { Profile, SourceSpec, Topic } from './state';
import { FoundCard, KIND_WORD, StarterList, hueOf } from './ui';

export function Sheet({ onClose, children }: { onClose: () => void; children: ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  useDragToClose(ref, onClose);
  return (
    <div className="scrim" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="sheet" ref={ref} role="dialog" aria-modal="true"><div className="grab" />{children}</div>
    </div>
  );
}

const sourceLine = (s: Source | undefined) => (s
  ? `${s.week.toLocaleString()} this week${isBusy(s) ? ' · very busy' : ''}`
  : 'Nothing from it in the last 30 days');

/* After creation, sources step back into settings: remove with a tap, search to
   add, muted words (VISION.md, "A topic's settings"). */
export function SettingsSheet({ topic, catalog, server, onChange, onDelete, onClose }: {
  topic: Topic; catalog: Map<string, Source>; server: boolean;
  onChange: (t: Topic) => void; onDelete: () => void; onClose: () => void;
}) {
  const [q, setQ] = useState('');
  const [web, setWeb] = useState<string | null>(null); // a search sent to the backend
  const discovery = useDiscovery(server ? web : null);
  const webFound = (discovery.result?.sources || []).filter((c) => !topic.sources.includes(c.name));
  const addFound = (spec: SourceSpec | undefined, name: string) => onChange({
    ...topic, sources: [...topic.sources, name], found: spec ? { ...(topic.found || {}), [name]: spec } : topic.found,
  });
  const searchWeb = (e: FormEvent) => { e.preventDefault(); if (q.trim().length >= 2) setWeb(q.trim()); };
  const [word, setWord] = useState('');
  const [confirm, setConfirm] = useState(false);
  const found = q.trim()
    ? [...catalog.values()].filter((s) => !topic.sources.includes(s.name) && s.name.toLowerCase().includes(q.trim().toLowerCase()))
      .sort((a, b) => b.week - a.week).slice(0, 12)
    : [];
  const mute = (e: FormEvent) => {
    e.preventDefault();
    const w = word.trim();
    if (w && !topic.muted.includes(w)) onChange({ ...topic, muted: [...topic.muted, w] });
    setWord('');
  };
  return (
    <Sheet onClose={onClose}>
      <div className="row"><h2 className="sheet-title">{topic.name}</h2><button className="x" onClick={onClose}>Done</button></div>
      <div className="section">
        <h3>Sources · {topic.sources.length}</h3>
        <div className="set-list">
          {topic.sources.map((name) => (
            <div className="set-item" key={name}>
              <div className="grow"><div className="strong">{name}</div><div className="sub">{sourceLine(catalog.get(name))}</div></div>
              <button className="x" onClick={() => onChange({ ...topic, sources: topic.sources.filter((s) => s !== name) })}>Remove</button>
            </div>
          ))}
          {topic.sources.length === 0 && <div className="set-item sub">No sources. Add one below.</div>}
        </div>
      </div>
      <div className="section">
        <h3>Add sources</h3>
        <form className="row" onSubmit={searchWeb}>
          <input className="field" id="add-source" autoComplete="off" style={{ flex: 1 }}
            placeholder={server ? 'A source by name, a subject, or paste a site' : 'Search sources by name'}
            value={q} onChange={(e) => { setQ(e.target.value); setWeb(null); }} />
          {server && <button className="btn" type="submit">Search</button>}
        </form>
        {q.trim() ? (
          <div className="set-list">
            {found.map((s) => (
              <div className="set-item wrap" key={s.name}>
                <div className="grow">
                  <div className="strong">{s.name}</div><div className="sub">{sourceLine(s)}</div>
                  {s.latest.length > 0 && <div className="sub pv-line">{s.latest.slice(0, 2).join(' · ')}</div>}
                </div>
                <button className="x add" onClick={() => onChange({ ...topic, sources: [...topic.sources, s.name] })}>Add</button>
              </div>
            ))}
            {found.length === 0 && !web && <div className="set-item sub">{server ? 'No source by that name yet. Search to look further.' : 'No source by that name yet.'}</div>}
            {web && discovery.loading && <div className="set-item sub">Searching…</div>}
            {web && discovery.error && <div className="set-item sub warn">{discovery.error}</div>}
            {web && webFound.filter((c) => !found.some((s) => s.name === c.name)).map((c) => (
              <div className="set-item wrap" key={`web:${c.name}`}>
                <div className="grow">
                  <div className="strong">{c.name}</div><div className="sub">{c.known ? sourceLine(asSource(c)) : `New · ${c.week} this week`}</div>
                  {c.latest.length > 0 && <div className="sub pv-line">{c.latest.slice(0, 2).join(' · ')}</div>}
                </div>
                <button className="x add" onClick={() => addFound(specsOf([c])[c.name], c.name)}>Add</button>
              </div>
            ))}
            {web && discovery.result?.note && <div className="set-item sub">{discovery.result.note}</div>}
          </div>
        ) : <div className="hint">{server
          ? 'Searches the sources Tributary reads, and with Search, the web.'
          : 'Searches the sources Tributary already reads. Searching the whole web comes with the backend.'}</div>}
      </div>
      <div className="section">
        <h3>Muted words</h3>
        <div className="chips">
          {topic.muted.map((w) => (
            <span key={w} className="chip muted-chip">{w}
              <button aria-label={`Unmute ${w}`} onClick={() => onChange({ ...topic, muted: topic.muted.filter((x) => x !== w) })}>×</button>
            </span>
          ))}
          {topic.muted.length === 0 && <span className="hint">Nothing muted.</span>}
        </div>
        <form className="row" onSubmit={mute}>
          <input className="field" id="mute" placeholder="Hide stories that mention…" value={word} onChange={(e) => setWord(e.target.value)} style={{ flex: 1 }} />
          <button className="btn" type="submit">Mute</button>
        </form>
      </div>
      <div className="section">
        {confirm
          ? <div className="row"><span className="grow">Remove {topic.name} and its sources?</span>
              <button className="btn" onClick={() => setConfirm(false)}>Keep</button>
              <button className="btn danger" onClick={onDelete}>Remove</button></div>
          : <button className="btn wide" onClick={() => setConfirm(true)}>Remove this topic</button>}
      </div>
      <p className="mock-note">Changes here affect only this topic.</p>
    </Sheet>
  );
}

/* Creating a topic: the one moment sources are the main event. */
export function NewTopicSheet({ bundle, catalog, profile, server, onCreate, onClose }: {
  bundle: Bundle; catalog: Map<string, Source>; profile: Profile; server: boolean;
  onCreate: (t: Topic) => void; onClose: () => void;
}) {
  const options = useMemo(() => shelves(bundle).filter((s) => !profile.topics.some((t) => t.id === s.slug)), [bundle, profile.topics]);
  const [pick, setPick] = useState<string | null>(null);
  const [chosen, setChosen] = useState<string[]>([]);
  const [typed, setTyped] = useState('');
  const [query, setQuery] = useState<string | null>(null);   // a subject or site sent to discovery
  const [ownChosen, setOwnChosen] = useState<string[] | undefined>(undefined);
  const [specs, setSpecs] = useState<Record<string, SourceSpec>>({});
  const [name, setName] = useState('');
  const choose = (slug: string) => { setPick(slug); setChosen(sourcesForShelf(catalog, slug).map((s) => s.name)); };
  const shelf = options.find((s) => s.slug === pick);
  const search = (e: FormEvent) => {
    e.preventDefault();
    const q = typed.trim();
    if (q.length < 2) return;
    setQuery(q); setName(q); setOwnChosen(undefined); setSpecs({});
  };
  /* Two topics cannot share an id, so a name already taken gets a number. */
  const freeId = (base: string) => {
    let id = base, n = 2;
    while (profile.topics.some((t) => t.id === id)) id = `${base}-${n++}`;
    return id;
  };
  const createOwn = () => {
    const sources = ownChosen || [];
    const found = Object.fromEntries(Object.entries(specs).filter(([n]) => sources.includes(n)));
    const title = name.trim() || query!;
    onCreate({ id: freeId(slugOf(title)), name: title, description: query, spine: null, sources, muted: [], found });
  };
  if (query) {
    return (
      <Sheet onClose={onClose}>
        <div className="row"><h2 className="sheet-title">Here's what we found</h2>
          <button className="x" onClick={onClose}>Cancel</button></div>
        <div className="section">
          <label className="eyebrow" htmlFor="topic-name">Call it</label>
          <input className="field" id="topic-name" value={name} onChange={(e) => setName(e.target.value)} />
        </div>
        <div style={{ marginTop: 12 }}>
          <DiscoveredCard query={query} chosen={ownChosen} setChosen={setOwnChosen}
            onFound={(all, found, title) => { setOwnChosen(all); setSpecs(found); if (title) setName(title); }} />
        </div>
        <div className="sticky-cta">
          <button className="btn ghost" onClick={() => setQuery(null)}>Back</button>
          <button className="btn primary wide" disabled={!ownChosen?.length} onClick={createOwn}>Create topic</button>
        </div>
      </Sheet>
    );
  }
  return (
    <Sheet onClose={onClose}>
      <div className="row"><h2 className="sheet-title">{shelf ? "Here's what we found" : 'New topic'}</h2>
        <button className="x" onClick={onClose}>Cancel</button></div>
      {!shelf ? (
        <div className="section">
          {server && (
            <form className="row" style={{ marginBottom: 12 }} onSubmit={search}>
              <input className="field" id="new-subject" placeholder="Any subject, or paste a site" autoComplete="off"
                value={typed} onChange={(e) => setTyped(e.target.value)} style={{ flex: 1 }} />
              <button className="btn" type="submit">Find</button>
            </form>
          )}
          <div className="area"><b>{STARTER_AREA}</b><span>the subjects Tributary reads today</span></div>
          <StarterList subjects={options} picked={[]} onPick={choose} single />
          {options.length === 0 && <span className="hint">You follow every {STARTER_AREA} subject Tributary reads today.</span>}
          {!server && <p className="hint">Subjects outside {STARTER_AREA}, with sources found on the web, come with the server.</p>}
        </div>
      ) : (
        <>
          <div style={{ marginTop: 12 }}>
            <FoundCard id={shelf.slug} name={shelf.name} sources={sourcesForShelf(catalog, shelf.slug)} chosen={chosen} setChosen={setChosen} />
          </div>
          <div className="sticky-cta">
            <button className="btn ghost" onClick={() => setPick(null)}>Back</button>
            <button className="btn primary wide" onClick={() => onCreate({ id: shelf.slug, name: shelf.name, spine: shelf.slug, sources: chosen, muted: [] })}>Create topic</button>
          </div>
        </>
      )}
    </Sheet>
  );
}

export function ProfileSheet({ profile, server, onTopic, onSwitch, onReset, onClose }: {
  profile: Profile; server: boolean; onTopic: (id: string) => void; onSwitch: () => void; onReset: () => void; onClose: () => void;
}) {
  const [confirm, setConfirm] = useState(false);
  return (
    <Sheet onClose={onClose}>
      <div className="row"><span className="avatar">{profile.name[0].toUpperCase()}</span>
        <h2 className="sheet-title">{profile.name}</h2><button className="x" onClick={onClose}>Done</button></div>
      <div className="section"><h3>Your topics</h3>
        <div className="set-list">
          {profile.topics.map((t) => (
            <button key={t.id} className="set-item as-button" onClick={() => onTopic(t.id)}>
              <span className="mini-face" style={{ background: hueOf(t.id) }}>{t.name[0]}</span>
              <span className="grow strong">{t.name}</span><span className="sub">{t.sources.length} sources</span>
            </button>
          ))}
        </div>
      </div>
      <div className="section stack">
        <button className="btn wide" onClick={onSwitch}>Switch profile</button>
        {confirm
          ? <div className="row"><span className="grow">Clear your topics and start the welcome again?</span>
              <button className="btn" onClick={() => setConfirm(false)}>Keep</button>
              <button className="btn danger" onClick={onReset}>Start over</button></div>
          : <button className="btn wide" onClick={() => setConfirm(true)}>Start over</button>}
      </div>
      <p className="mock-note">A profile is just a name for now — no password. {server ? 'It lives on this computer\'s server, so every device that opens it sees the same one.' : 'It lives on this device.'}</p>
    </Sheet>
  );
}

/* A story: what happened, and everything attached to it, each linking out. */
export function StorySheet({ story, onClose }: { story: Story; onClose: () => void }) {
  return (
    <Sheet onClose={onClose}>
      <div className="row"><span className="eyebrow grow">{KIND_WORD[story.kind] || story.kind} · {agoLabel(story.published_at)}</span>
        <button className="x" onClick={onClose}>Close</button></div>
      <h2 className="story-title">{story.title}</h2>
      {story.summary && <p className="story-sum">{story.summary}</p>}
      <a className="btn primary wide link-btn" href={story.url} target="_blank" rel="noopener noreferrer">Read at {story.source}</a>
      {story.items.length > 1 && (
        <div className="section"><h3>Also in this story · {story.items.length - 1}</h3>
          <div className="set-list">
            {story.items.slice(1).map((it) => (
              <a key={it.url} className="set-item as-button" href={it.url} target="_blank" rel="noopener noreferrer">
                <span className="grow"><span className="strong block">{it.title}</span>
                  <span className="sub">{it.source} · {KIND_WORD[it.kind] || it.kind} · {agoLabel(it.published_at)}</span></span>
              </a>
            ))}
          </div>
        </div>
      )}
    </Sheet>
  );
}
