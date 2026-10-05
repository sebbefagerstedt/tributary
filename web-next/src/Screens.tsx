/* Home and a topic's page. Each has two views of one place, not separate tabs
   (VISION.md): Topics, the boxes of what is under it, and Feed, its stories. */

import { Bundle, Label, STARTER_AREA, Story } from './data';
import { Profile, Topic, byNewest, inTopic, isNew } from './state';
import { Caught, ICON, LayoutSwitch, StoryCard, hueOf } from './ui';

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

/* Topics as boxes: each wears its newest picture (or its colour), its new
   count and its latest headline, and opens that topic. The same boxes are a
   topic's subtopics on its own page -- "Topics" is the map, "Feed" the reader. */
interface Box { key: string; name: string; hue: string; list: Story[]; open: () => void }

function SubjectTiles({ boxes, profile }: { boxes: Box[]; profile: Profile }) {
  return (
    <div className="tiles">
      {boxes.map((b) => {
        const n = b.list.filter((s) => isNew(profile, s)).length;
        const art = b.list.find((s) => s.media_url)?.media_url;
        return (
          <button key={b.key} className="tile" style={{ background: b.hue }} onClick={b.open}>
            {art ? <img src={art} alt="" loading="lazy" referrerPolicy="no-referrer" /> : <span className="glyph">{b.name[0]}</span>}
            <span className="shade" />
            <span className="tx">
              {n > 0 && <span className="nw">{n} new</span>}
              <span className="nm">{b.name}</span>
              <span className="ld">{b.list[0] ? b.list[0].title : 'Quiet right now'}</span>
            </span>
          </button>
        );
      })}
    </div>
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
        <div><div className="eyebrow">Your topics</div>
          <div className="count">{fresh} new · {mine.length} stories</div></div>
        <LayoutSwitch value={profile.layout} onChange={nav.setLayout} />
      </div>
      {profile.layout === 'grid'
        ? <SubjectTiles profile={profile} boxes={profile.topics.map((t) => ({
            key: t.id, name: t.name, hue: hueOf(t.id), list: storiesOf(bundle, t), open: () => nav.openTopic(t.id) }))} />
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
  const subs = leaf ? [] : leaves;
  const view = subs.length ? profile.layout : 'cards';
  // What the topic holds: a starter's shelf description, or what you typed.
  const shelfAbout = topic.spine ? bundle.spine.find((l) => l.slug === topic.spine)?.description : null;
  const raw = shelfAbout ? `${STARTER_AREA}: ${shelfAbout}` : topic.description && topic.description !== topic.name ? topic.description : null;
  const about = raw && raw[0].toUpperCase() + raw.slice(1);
  return (
    <>
      <div className="bar">
        <button className="icon-btn" onClick={nav.back} aria-label="Back">{ICON.back}</button>
        <div className="grow">
          <div className="crumbs">{leafName
            ? <button className="crumb" onClick={() => nav.openTopic(topic.id)}>{topic.name}</button> : topic.spine ? STARTER_AREA : 'Your topic'}</div>
          <div className="title-sm">{leafName || topic.name}</div>
        </div>
        <button className="icon-btn" onClick={() => nav.openSettings(topic)} aria-label="Topic settings">{ICON.gear}</button>
      </div>
      <div className="topic-hero" style={{ background: hueOf(topic.id) }}>
        <h1>{leafName || topic.name}</h1>
        {!leaf && about && <p className="about">{about}</p>}
        <div className="stat">{n} new · {list.length} stories · {topic.sources.length} sources</div>
        <div className="row">
          <button className="btn solid" onClick={() => nav.play(topic, leaf)} disabled={!list.length}>{n ? 'Play new' : 'Play latest'}</button>
          <button className="btn" onClick={() => nav.openSettings(topic)}>Sources &amp; settings</button>
        </div>
      </div>
      {/* Topics shows the subtopics as boxes; a place with none under it only
          has a feed, so it shows that without offering a switch. */}
      <div className="toolbar">
        <div className="eyebrow">{view === 'grid' ? 'Subtopics' : 'Stories'}</div>
        {subs.length > 0 && <LayoutSwitch value={profile.layout} onChange={nav.setLayout} />}
      </div>
      {view === 'grid'
        ? <SubjectTiles profile={profile} boxes={subs.map((l) => ({
            key: l.slug, name: l.name, hue: hueOf(topic.id), list: storiesOf(bundle, topic, l.slug),
            open: () => nav.openTopic(topic.id, l.slug) }))} />
        : list.length === 0
          ? <div className="empty">Nothing here yet. Add sources in this topic's settings.</div>
          : <Cards list={list} profile={profile} topics={profile.topics} here={topic.id} nav={nav} shown={shown} more={more} />}
    </>
  );
}
