/* Home and a topic's page. Both show stories one of two ways — the layouts of
   one place, not separate tabs (VISION.md). */

import { Bundle, Label, Story, agoLabel } from './data';
import { Profile, Topic, byNewest, inTopic, isNew, isSeen } from './state';
import { Caught, ICON, KIND_WORD, LayoutSwitch, StoryCard, hueOf, kindColour } from './ui';

export interface Nav {
  openTopic: (id: string, leaf?: string) => void;
  openStory: (s: Story) => void;
  play: (topic: Topic, leaf?: string) => void;
  openTree: () => void;
  openProfile: () => void;
  openSettings: (topic: Topic) => void;
  newTopic: () => void;
  back: () => void;
  setLayout: (l: Profile['layout']) => void;
}

export const storiesOf = (bundle: Bundle, topic: Topic, leaf?: string) =>
  bundle.stories.filter((s) => inTopic(s, topic, leaf)).sort(byNewest);

export function myStories(bundle: Bundle, profile: Profile) {
  return bundle.stories.filter((s) => profile.topics.some((t) => inTopic(s, t))).sort(byNewest);
}

function Rings({ bundle, profile, nav }: { bundle: Bundle; profile: Profile; nav: Nav }) {
  return (
    <div className="rings">
      {profile.topics.map((t) => {
        const n = storiesOf(bundle, t).filter((s) => isNew(profile, s)).length;
        return (
          <button key={t.id} className={`ring ${n ? 'new' : ''}`}
            onClick={() => (n ? nav.play(t) : nav.openTopic(t.id))}>
            <span className="disc"><span className="face" style={{ background: hueOf(t.id) }}>{t.name[0]}</span></span>
            <span className="nm">{t.name}</span>
            <span className="ct">{n ? `${n} new` : 'all read'}</span>
          </button>
        );
      })}
      <button className="ring add" onClick={nav.newTopic}>
        <span className="disc"><span className="face">+</span></span><span className="nm">New topic</span><span className="ct">&nbsp;</span>
      </button>
    </div>
  );
}

function TopicTiles({ bundle, profile, nav }: { bundle: Bundle; profile: Profile; nav: Nav }) {
  return (
    <div className="tiles">
      {profile.topics.map((t) => {
        const list = storiesOf(bundle, t);
        const n = list.filter((s) => isNew(profile, s)).length;
        const art = list.find((s) => s.media_url)?.media_url;
        return (
          <button key={t.id} className="tile" style={{ background: hueOf(t.id) }} onClick={() => nav.openTopic(t.id)}>
            {art ? <img src={art} alt="" loading="lazy" referrerPolicy="no-referrer" /> : <span className="glyph">{t.name[0]}</span>}
            <span className="shade" />
            <span className="tx">
              {n > 0 && <span className="nw">{n} new</span>}
              <span className="nm">{t.name}</span>
              <span className="ld">{list[0] ? list[0].title : 'Quiet right now'}</span>
            </span>
          </button>
        );
      })}
    </div>
  );
}

function StoryTiles({ list, profile, nav, shown, more }: { list: Story[]; profile: Profile; nav: Nav; shown: number; more: () => void }) {
  return (
    <>
      <div className="tiles">
        {list.slice(0, shown).map((s) => (
          <button key={s.story_id} className="tile" onClick={() => nav.openStory(s)}
            style={{ background: kindColour(s.kind), opacity: isSeen(profile, s) ? 0.6 : 1 }}>
            {s.media_url && <img src={s.media_url} alt="" loading="lazy" referrerPolicy="no-referrer" />}
            <span className="shade" />
            <span className="tx">
              {isNew(profile, s) && <span className="nw">New</span>}
              <span className="ld story">{s.title}</span>
              <span className="ld">{KIND_WORD[s.kind] || s.kind} · {s.source} · {agoLabel(s.published_at)}</span>
            </span>
          </button>
        ))}
      </div>
      {list.length > shown
        ? <button className="btn wide more" onClick={more}>Show {Math.min(50, list.length - shown)} more · {list.length - shown} left</button>
        : <Caught />}
    </>
  );
}

/* New first, then "You're all caught up", then the rest under Earlier. Fifty at a
   time behind a button, never refilling on scroll (VISION.md, principle 6). */
function Cards({ list, profile, topics, here, nav, shown, more }: {
  list: Story[]; profile: Profile; topics: Topic[]; here?: string; nav: Nav; shown: number; more: () => void;
}) {
  const fresh = list.filter((s) => isNew(profile, s));
  const rest = list.filter((s) => !isNew(profile, s));
  const card = (s: Story) => (
    <StoryCard key={s.story_id} story={s} profile={profile} topics={topics} here={here}
      onOpen={nav.openStory} onTopic={nav.openTopic} />
  );
  return (
    <>
      <div className="stack">{fresh.map(card)}</div>
      <Caught note={fresh.length ? 'Nothing else new from the last 48 hours.' : 'Nothing new from the last 48 hours.'} />
      {rest.length > 0 && (
        <>
          <div className="eyebrow older-label">Earlier</div>
          <div className="stack">{rest.slice(0, shown).map(card)}</div>
          {rest.length > shown && (
            <button className="btn wide more" onClick={more}>Show {Math.min(50, rest.length - shown)} more · {rest.length - shown} left</button>
          )}
        </>
      )}
    </>
  );
}

export function Home({ bundle, profile, nav, shown, more }: {
  bundle: Bundle; profile: Profile; nav: Nav; shown: number; more: () => void;
}) {
  const mine = myStories(bundle, profile);
  const fresh = mine.filter((s) => isNew(profile, s)).length;
  return (
    <>
      <div className="bar">
        <div className="wordmark grow">Tributary<i>.</i></div>
        <button className="icon-btn" onClick={nav.openTree} aria-label="Explore your tree">{ICON.tree}</button>
        <button className="avatar" onClick={nav.openProfile} aria-label="Profile">{profile.name[0].toUpperCase()}</button>
      </div>
      <Rings bundle={bundle} profile={profile} nav={nav} />
      <div className="toolbar">
        <div><div className="eyebrow">Everything you follow</div>
          <div className="count">{fresh} new · {mine.length} stories</div></div>
        <LayoutSwitch value={profile.layout} onChange={nav.setLayout} />
      </div>
      {profile.layout === 'grid'
        ? <TopicTiles bundle={bundle} profile={profile} nav={nav} />
        : <Cards list={mine} profile={profile} topics={profile.topics} nav={nav} shown={shown} more={more} />}
    </>
  );
}

export function TopicPage({ bundle, profile, topic, leaf, nav, shown, more }: {
  bundle: Bundle; profile: Profile; topic: Topic; leaf?: string; nav: Nav; shown: number; more: () => void;
}) {
  const list = storiesOf(bundle, topic, leaf);
  const n = list.filter((s) => isNew(profile, s)).length;
  const leaves: Label[] = topic.spine ? bundle.spine.filter((l) => l.parent === topic.spine) : [];
  const leafName = leaf && leaves.find((l) => l.slug === leaf)?.name;
  return (
    <>
      <div className="bar">
        <button className="icon-btn" onClick={nav.back} aria-label="Back">{ICON.back}</button>
        <div className="grow">
          <div className="crumbs">{leafName
            ? <button className="crumb" onClick={() => nav.openTopic(topic.id)}>{topic.name}</button> : 'Topic'}</div>
          <div className="title-sm">{leafName || topic.name}</div>
        </div>
        <button className="icon-btn" onClick={() => nav.openSettings(topic)} aria-label="Topic settings">{ICON.gear}</button>
      </div>
      <div className="topic-hero" style={{ background: hueOf(topic.id) }}>
        <h1>{leafName || topic.name}</h1>
        <div className="stat">{n} new · {list.length} stories · {topic.sources.length} sources</div>
        <div className="row">
          <button className="btn solid" onClick={() => nav.play(topic, leaf)} disabled={!list.length}>{n ? 'Play new' : 'Play latest'}</button>
          <button className="btn" onClick={() => nav.openSettings(topic)}>Sources &amp; settings</button>
        </div>
      </div>
      {!leaf && leaves.length > 0 && (
        <div className="chips" style={{ marginBottom: 12 }}>
          {leaves.map((l) => <button key={l.slug} className="chip" onClick={() => nav.openTopic(topic.id, l.slug)}>{l.name}</button>)}
        </div>
      )}
      <div className="toolbar"><div className="eyebrow">Stories</div><LayoutSwitch value={profile.layout} onChange={nav.setLayout} /></div>
      {list.length === 0 && <div className="empty">Nothing here yet. Add sources in this topic's settings.</div>}
      {list.length > 0 && (profile.layout === 'grid'
        ? <StoryTiles list={list} profile={profile} nav={nav} shown={shown} more={more} />
        : <Cards list={list} profile={profile} topics={profile.topics} here={topic.id} nav={nav} shown={shown} more={more} />)}
    </>
  );
}
