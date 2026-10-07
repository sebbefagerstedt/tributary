/* Sheets slide over the screen you are on: a topic's settings, a new topic,
   your profile, and a story. Each is one level of "back". */

import { FormEvent, ReactNode, useMemo, useRef, useState } from 'react';
import { Bundle, ROOT, Source, Story, agoLabel, categories, childrenOf, isBusy, nodeOf, pathTo, sourcesFor } from './data';
import { useDragToClose } from './gestures';
import { DiscoveredCard, asSource, slugOf, specsOf, useDiscovery } from './Discovery';
import { Profile, SourceSpec, Topic, eventTopic, freeId, likeExamples, namedIn, shortName, words } from './state';
import { FoundCard, KIND_WORD, SpecificChips, hueOf } from './ui';

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

/* The tree as rows you can walk down, any depth: a row with topics under it
   opens them, a row without is picked. Inside a topic, "All of" picks the
   topic itself -- so a subtopic is found without following its topic first. */
function TreeChooser({ bundle, at, setAt, followed, onPick }: {
  bundle: Bundle; at: string | null; setAt: (slug: string | null) => void;
  followed: (slug: string) => boolean; onPick: (slug: string) => void;
}) {
  const here = at ? nodeOf(bundle, at) : undefined;
  const rows = childrenOf(bundle, at);
  const hue = (slug: string) => hueOf(pathTo(bundle, slug)[0]?.slug ?? slug);
  const about = (d?: string | null) => d && d[0].toUpperCase() + d.slice(1);
  return (
    <>
      <div className="area">
        {here
          ? <button className="crumb" onClick={() => setAt(here.parent ?? null)}>‹ {here.parent ? nodeOf(bundle, here.parent)?.name : ROOT}</button>
          : <><b>{ROOT}</b><span>the subjects Tributary reads today</span></>}
      </div>
      <div className="starters" role="list">
        {here && (
          <button role="listitem" className="starter all" disabled={followed(here.slug)} onClick={() => onPick(here.slug)}>
            <span className="em" style={{ background: hue(here.slug) }}>{here.name[0]}</span>
            <span className="grow"><span className="strong block">All of {here.name}</span>
              <span className="sub block">{followed(here.slug) ? 'You follow this' : 'Everything below, in one topic'}</span></span>
            {followed(here.slug) ? <span className="done">✓</span> : <span className="go" aria-hidden="true">+</span>}
          </button>
        )}
        {rows.map((c) => {
          const inside = childrenOf(bundle, c.slug).length;
          const mine = followed(c.slug);
          return (
            <button key={c.slug} role="listitem" className="starter" disabled={mine && !inside}
              onClick={() => (inside ? setAt(c.slug) : onPick(c.slug))}>
              <span className="em" style={{ background: hue(c.slug) }}>{c.name[0]}</span>
              <span className="grow"><span className="strong block">{c.name}</span>
                <span className="sub block">{mine ? 'You follow this' : inside ? `${inside} topics inside` : about(c.description)}</span></span>
              {inside ? <span className="go" aria-hidden="true">›</span> : mine ? <span className="done">✓</span> : <span className="go" aria-hidden="true">+</span>}
            </button>
          );
        })}
      </div>
    </>
  );
}

/* Creating a topic: the one moment sources are the main event. */
export function NewTopicSheet({ bundle, catalog, profile, server, onCreate, onClose }: {
  bundle: Bundle; catalog: Map<string, Source>; profile: Profile; server: boolean;
  onCreate: (t: Topic) => void; onClose: () => void;
}) {
  const followed = (slug: string) => profile.topics.some((t) => t.spine === slug);
  const specific = useMemo(() => categories(bundle).flatMap((c) => childrenOf(bundle, c.slug)).filter((s) => !followed(s.slug)), // eslint-disable-next-line react-hooks/exhaustive-deps
    [bundle, profile.topics]);
  const [pick, setPick] = useState<string | null>(null);
  // Where you are in the tree while choosing: null is News, the top.
  const [at, setAt] = useState<string | null>(null);
  const [chosen, setChosen] = useState<string[]>([]);
  const [typed, setTyped] = useState('');
  const [query, setQuery] = useState<string | null>(null);   // a subject or site sent to discovery
  const [ownChosen, setOwnChosen] = useState<string[] | undefined>(undefined);
  const [specs, setSpecs] = useState<Record<string, SourceSpec>>({});
  const [name, setName] = useState('');
  const choose = (slug: string) => { setPick(slug); setChosen(sourcesFor(catalog, slug).map((s) => s.name)); };
  const shelf = pick ? nodeOf(bundle, pick) : undefined;
  const search = (e: FormEvent) => {
    e.preventDefault();
    const q = typed.trim();
    if (q.length < 2) return;
    setQuery(q); setName(q); setOwnChosen(undefined); setSpecs({});
  };
  const createOwn = () => {
    const sources = ownChosen || [];
    const found = Object.fromEntries(Object.entries(specs).filter(([n]) => sources.includes(n)));
    const title = name.trim() || query!;
    onCreate({ id: freeId(profile, slugOf(title)), name: title, description: query, spine: null, sources, muted: [], found });
  };
  /* Without a server nothing can search the web or embed a description, so a
     subject of your own is its words, over every source Tributary reads --
     and what it would hold is shown before it is made. */
  if (query && !server) {
    const draft: Topic = { id: '', name: name.trim() || query, description: query, spine: null,
      sources: [...catalog.keys()], muted: [] };
    const held = bundle.stories.filter((s) => namedIn(s, draft.name));
    const asked = words(draft.name);
    return (
      <Sheet onClose={onClose}>
        <div className="row"><h2 className="sheet-title">Here's what it would hold</h2>
          <button className="x" onClick={onClose}>Cancel</button></div>
        <div className="section">
          <label className="eyebrow" htmlFor="topic-name">Call it</label>
          <input className="field" id="topic-name" value={name} onChange={(e) => setName(e.target.value)} autoComplete="off" />
          <p className="hint">{asked.length
            ? <>Stories that mention {asked.map((w, i) => <span key={w}>{i > 0 && (i === asked.length - 1 ? ' and ' : ', ')}<b>{w}</b></span>)}, from every source Tributary reads.</>
            : 'Give it a word or two to look for.'}</p>
        </div>
        <div className="section">
          <h3>{held.length ? `${held.length} ${held.length === 1 ? 'story' : 'stories'} so far` : 'Nothing yet'}</h3>
          {held.length > 0 ? (
            <ul className="follow-preview">
              {held.slice(0, 6).map((s) => <li key={s.story_id}>{s.title} <span className="sub">· {s.source}, {agoLabel(s.published_at)}</span></li>)}
              {held.length > 6 && <li className="sub">and {held.length - 6} more</li>}
            </ul>
          ) : <p className="hint">New stories that mention it will land here as they arrive. Fewer or more general words catch more.</p>}
        </div>
        <p className="hint">Finding new sources for a subject comes with the server.</p>
        <div className="sticky-cta">
          <button className="btn ghost" onClick={() => setQuery(null)}>Back</button>
          <button className="btn primary wide" disabled={!asked.length}
            onClick={() => onCreate({ ...draft, id: freeId(profile, slugOf(draft.name)) })}>Create topic</button>
        </div>
      </Sheet>
    );
  }
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
          <form className="row" style={{ marginBottom: 12 }} onSubmit={search}>
            <input className="field" id="new-subject" autoComplete="off"
              placeholder={server ? 'Any subject, or paste a site' : 'Any subject: a name, a place, a thing'}
              value={typed} onChange={(e) => setTyped(e.target.value)} style={{ flex: 1 }} />
            <button className="btn" type="submit">{server ? 'Find' : 'Look'}</button>
          </form>
          <TreeChooser bundle={bundle} at={at} setAt={setAt} followed={followed} onPick={choose} />
          {at === null && <SpecificChips subjects={specific} picked={[]} onPick={choose} />}
        </div>
      ) : (
        <>
          <div style={{ marginTop: 12 }}>
            <FoundCard id={shelf.slug} name={shelf.name} sources={sourcesFor(catalog, shelf.slug)} chosen={chosen} setChosen={setChosen} />
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
/* Following one event: the story you are reading becomes a topic of its own,
   holding it and whatever comes close to it later -- the follow-ups, the
   reactions, the next development. Shown before you follow: what it would
   already hold, so the bar it uses is never a surprise. */
function FollowStory({ story, bundle, profile, catalog, onFollow, onOpenTopic }: {
  story: Story; bundle: Bundle; profile: Profile; catalog: Map<string, Source>;
  onFollow: (t: Topic) => void; onOpenTopic: (id: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState(() => shortName(story.title));
  const mine = profile.topics.find((t) => t.examples?.includes(story.story_id));
  const draft = useMemo(() => eventTopic(story, name.trim() || story.title, [...catalog.keys()], ''),
    [story, name, catalog]);
  const others = useMemo(() => (open ? bundle.stories.filter((s) => s.story_id !== story.story_id && likeExamples(s, draft)) : []),
    [open, bundle, story, draft]);
  if (mine) {
    return (
      <button className="btn wide follow-story on" onClick={() => onOpenTopic(mine.id)}>✓ Following as “{mine.name}” ›</button>
    );
  }
  if (!open) return <button className="btn wide follow-story" onClick={() => setOpen(true)}>Follow this story</button>;
  return (
    <div className="follow-panel">
      <h3>Follow this story</h3>
      <p className="sub">Becomes a topic of yours: this story, and whatever comes close to it later — follow-ups, reactions, what happens next.</p>
      <label className="eyebrow" htmlFor="event-name">Call it</label>
      <input className="field" id="event-name" value={name} onChange={(e) => setName(e.target.value)} autoComplete="off" />
      <div className="sub follow-count">{others.length
        ? `${others.length} other ${others.length === 1 ? 'story' : 'stories'} already close to it:`
        : 'Nothing else close to it yet — new stories join as they arrive.'}</div>
      {others.length > 0 && (
        <ul className="follow-preview">
          {others.slice(0, 4).map((s) => <li key={s.story_id}>{s.title} <span className="sub">· {s.source}, {agoLabel(s.published_at)}</span></li>)}
          {others.length > 4 && <li className="sub">and {others.length - 4} more</li>}
        </ul>
      )}
      <div className="row">
        <button className="btn ghost" onClick={() => setOpen(false)}>Cancel</button>
        <button className="btn primary wide" disabled={!name.trim()}
          onClick={() => onFollow({ ...draft, id: freeId(profile, slugOf(name.trim())) })}>Follow</button>
      </div>
    </div>
  );
}

export function StorySheet({ story, bundle, profile, catalog, onFollow, onOpenTopic, onClose }: {
  story: Story; bundle: Bundle; profile: Profile; catalog: Map<string, Source>;
  onFollow: (t: Topic) => void; onOpenTopic: (id: string) => void; onClose: () => void;
}) {
  return (
    <Sheet onClose={onClose}>
      <div className="row"><span className="eyebrow grow">{KIND_WORD[story.kind] || story.kind} · {agoLabel(story.published_at)}</span>
        <button className="x" onClick={onClose}>Close</button></div>
      <h2 className="story-title">{story.title}</h2>
      {story.summary && <p className="story-sum">{story.summary}</p>}
      <a className="btn primary wide link-btn" href={story.url} target="_blank" rel="noopener noreferrer">Read at {story.source}</a>
      <FollowStory story={story} bundle={bundle} profile={profile} catalog={catalog} onFollow={onFollow} onOpenTopic={onOpenTopic} />
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
