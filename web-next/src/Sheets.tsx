/* Sheets slide over the screen you are on: a topic's settings, a new topic,
   your profile, and a story. Each is one level of "back". */

import { FormEvent, ReactNode, useMemo, useState } from 'react';
import { Bundle, Source, Story, agoLabel, isBusy, shelves, sourcesForShelf } from './data';
import { Profile, Topic } from './state';
import { FoundCard, KIND_WORD, hueOf } from './ui';

export function Sheet({ onClose, children }: { onClose: () => void; children: ReactNode }) {
  return (
    <div className="scrim" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="sheet" role="dialog" aria-modal="true"><div className="grab" />{children}</div>
    </div>
  );
}

const sourceLine = (s: Source | undefined) => (s
  ? `${s.week.toLocaleString()} this week${isBusy(s) ? ' · very busy' : ''}`
  : 'Nothing from it in the last 30 days');

/* After creation, sources step back into settings: remove with a tap, search to
   add, muted words (VISION.md, "A topic's settings"). */
export function SettingsSheet({ topic, catalog, onChange, onDelete, onClose }: {
  topic: Topic; catalog: Map<string, Source>; onChange: (t: Topic) => void; onDelete: () => void; onClose: () => void;
}) {
  const [q, setQ] = useState('');
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
        <input className="field" id="add-source" placeholder="Search sources by name" value={q} autoComplete="off"
          onChange={(e) => setQ(e.target.value)} />
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
            {found.length === 0 && <div className="set-item sub">No source by that name yet.</div>}
          </div>
        ) : <div className="hint">Searches the sources Tributary already reads. Searching the whole web comes with the backend.</div>}
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
export function NewTopicSheet({ bundle, catalog, profile, onCreate, onClose }: {
  bundle: Bundle; catalog: Map<string, Source>; profile: Profile; onCreate: (t: Topic) => void; onClose: () => void;
}) {
  const options = useMemo(() => shelves(bundle).filter((s) => !profile.topics.some((t) => t.id === s.slug)), [bundle, profile.topics]);
  const [pick, setPick] = useState<string | null>(null);
  const [chosen, setChosen] = useState<string[]>([]);
  const choose = (slug: string) => { setPick(slug); setChosen(sourcesForShelf(catalog, slug).map((s) => s.name)); };
  const shelf = options.find((s) => s.slug === pick);
  return (
    <Sheet onClose={onClose}>
      <div className="row"><h2 className="sheet-title">{shelf ? "Here's what we found" : 'New topic'}</h2>
        <button className="x" onClick={onClose}>Cancel</button></div>
      {!shelf ? (
        <div className="section">
          <div className="chips">{options.map((s) => <button key={s.slug} className="chip" onClick={() => choose(s.slug)}>{s.name}</button>)}</div>
          {options.length === 0 && <span className="hint">You follow every subject Tributary reads today.</span>}
          <p className="hint">Naming any subject, or pasting a site, arrives with the backend.</p>
        </div>
      ) : (
        <>
          <div style={{ marginTop: 12 }}>
            <FoundCard id={shelf.slug} name={shelf.name} sources={sourcesForShelf(catalog, shelf.slug)} chosen={chosen} setChosen={setChosen} />
          </div>
          <div className="sticky-cta">
            <button className="btn ghost" onClick={() => setPick(null)}>Back</button>
            <button className="btn primary wide" onClick={() => onCreate({ id: shelf.slug, name: shelf.name, sources: chosen, muted: [] })}>Create topic</button>
          </div>
        </>
      )}
    </Sheet>
  );
}

export function ProfileSheet({ profile, onTopic, onSwitch, onReset, onClose }: {
  profile: Profile; onTopic: (id: string) => void; onSwitch: () => void; onReset: () => void; onClose: () => void;
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
      <p className="mock-note">A profile is just a name for now — no password. It lives on this device.</p>
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
