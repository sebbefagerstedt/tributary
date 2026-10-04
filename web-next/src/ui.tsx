import { Source, Story, agoLabel, isBusy } from './data';
import { Profile, Topic, isNew, isSeen } from './state';

export const ICON = {
  back: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><path d="M15 18l-6-6 6-6" /></svg>,
  grid: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3.5" y="3.5" width="7" height="7" rx="1.5" /><rect x="13.5" y="3.5" width="7" height="7" rx="1.5" /><rect x="3.5" y="13.5" width="7" height="7" rx="1.5" /><rect x="13.5" y="13.5" width="7" height="7" rx="1.5" /></svg>,
  cards: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="4" y="3.5" width="16" height="10" rx="2" /><path d="M4 17.5h16M4 20.5h10" /></svg>,
  gear: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><circle cx="12" cy="12" r="3" /><path d="M12 2.5v3M12 18.5v3M2.5 12h3M18.5 12h3M5.3 5.3l2.1 2.1M16.6 16.6l2.1 2.1M5.3 18.7l2.1-2.1M16.6 7.4l2.1-2.1" /></svg>,
  tree: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><circle cx="12" cy="5" r="2.2" /><circle cx="5" cy="18" r="2.2" /><circle cx="19" cy="18" r="2.2" /><circle cx="12" cy="18" r="2.2" /><path d="M12 7.2v8.6M10.6 6.6 6.2 16M13.4 6.6l4.4 9.4" /></svg>,
  check: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><path d="M5 12.5l4.5 4.5L19 7.5" /></svg>,
};

/* A colour per topic, stable from its id, so a topic is recognisable before it
   is read. Deep enough for white text in both themes. */
const HUES = ['#4f58c9', '#23735f', '#c24a2c', '#2b4f8f', '#8a3fb0', '#b5527c', '#3d6a5a', '#c0761b', '#7a5230', '#2f7d8c'];
let order: string[] = [];
/* Colours go to subjects in spine order, so ten shelves get ten colours; a
   hash alone gave two of them the same purple. Anything unknown is hashed. */
export const setHueOrder = (ids: string[]) => { order = ids; };
export const hueOf = (id: string) => {
  const at = order.indexOf(id);
  if (at >= 0) return HUES[at % HUES.length];
  let h = 0;
  for (const ch of id) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  return HUES[h % HUES.length];
};

export const KIND_WORD: Record<string, string> = {
  paper: 'Paper', model: 'Model', repo: 'Release', video: 'Video', discussion: 'Discussion', article: 'Article', post: 'Post',
};
const KIND_VAR: Record<string, string> = {
  paper: 'paper', model: 'release', repo: 'release', video: 'video', discussion: 'discussion', article: 'article', post: 'article',
};
export const kindColour = (kind: string) => `var(--k-${KIND_VAR[kind] || 'article'})`;

export function LayoutSwitch({ value, onChange }: { value: Profile['layout']; onChange: (v: Profile['layout']) => void }) {
  return (
    <div className="switch" role="group" aria-label="Layout">
      <button aria-pressed={value === 'grid'} onClick={() => onChange('grid')}>{ICON.grid}Overview</button>
      <button aria-pressed={value === 'cards'} onClick={() => onChange('cards')}>{ICON.cards}Read</button>
    </div>
  );
}

export function Caught({ note }: { note?: string }) {
  return (
    <div className="caught">
      <span className="tick">{ICON.check}</span>
      <b>You're all caught up</b>
      {note && <span>{note}</span>}
    </div>
  );
}

export function SourceRow({ src, on, onToggle }: { src: Source; on: boolean; onToggle: () => void }) {
  return (
    <details className="src-row">
      <summary>
        <button className="check" role="checkbox" aria-checked={on} aria-label={`Include ${src.name}`}
          onClick={(e) => { e.preventDefault(); onToggle(); }}>{on && ICON.check}</button>
        <div>
          <div className="nm">{src.name}</div>
          <div className="sub">
            {src.week.toLocaleString()} this week
            {isBusy(src) && <> · <span className="warn">very busy</span></>}
          </div>
        </div>
        <span className="peek">Preview</span>
      </summary>
      <div className="pv">{src.latest.map((t) => <div key={t}>{t}</div>)}</div>
    </details>
  );
}

/* "Here is what we found" for one subject: its sources with previews, all
   ticked, with Include all as the easy path. Used by the first run and by
   creating a topic. */
export function FoundCard({ name, id, sources, chosen, setChosen }: {
  name: string; id: string; sources: Source[]; chosen: string[]; setChosen: (next: string[]) => void;
}) {
  const all = sources.length > 0 && chosen.length === sources.length;
  return (
    <div className="found">
      <div className="found-head">
        <span className="sq" style={{ background: hueOf(id) }}>{name[0]}</span>
        <div className="grow"><h3>{name}</h3><small>{sources.length} sources found · {chosen.length} selected</small></div>
      </div>
      {sources.length > 0 && (
        <div className="all-row">
          <span>{all ? 'All sources included' : 'Some sources selected'}</span>
          <button className="btn ghost" onClick={() => setChosen(all ? [] : sources.map((s) => s.name))}>
            {all ? 'Pick a few' : 'Include all'}</button>
        </div>
      )}
      {sources.map((s) => (
        <SourceRow key={s.name} src={s} on={chosen.includes(s.name)}
          onToggle={() => setChosen(chosen.includes(s.name) ? chosen.filter((x) => x !== s.name) : [...chosen, s.name])} />
      ))}
      {sources.length === 0 && <div className="src-row"><span className="sub">No sources cover this yet.</span></div>}
    </div>
  );
}

export function StoryCard({ story, profile, topics, here, onOpen, onTopic }: {
  story: Story; profile: Profile; topics: Topic[]; here?: string;
  onOpen: (s: Story) => void; onTopic: (id: string, leaf?: string) => void;
}) {
  const places = topics.filter((t) => story.topics.some((l) => (l.parent || l.slug) === t.id));
  const leaf = story.topics.find((l) => l.parent)?.name;
  return (
    <article className={`card ${isSeen(profile, story) ? 'read' : ''}`}>
      <button className="cover" style={{ background: kindColour(story.kind) }} onClick={() => onOpen(story)}>
        {story.media_url && <img className="cover-img" src={story.media_url} alt="" loading="lazy" referrerPolicy="no-referrer"
          onError={(e) => { (e.target as HTMLImageElement).remove(); }} />}
        <span className="kind">{KIND_WORD[story.kind] || story.kind}</span>
        <h3>{story.title}</h3>
      </button>
      <div className="meta">
        <div className="line1">
          {isNew(profile, story) && <span className="dot" title="New" />}
          <span className="src">{story.source}</span>
          <span>{agoLabel(story.published_at)}</span>
          {story.sources > 1 && <span>· {story.sources} sources</span>}
        </div>
        {story.summary && <div className="sum">{story.summary}</div>}
        <div className="chips">
          {places.map((p) => (
            <button key={p.id} className="chip place" onClick={() => onTopic(p.id)}>
              {p.name}{leaf && p.id === here ? ` › ${leaf}` : ''}
            </button>
          ))}
        </div>
      </div>
    </article>
  );
}
