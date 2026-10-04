import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Bundle, Story, buildCatalog, loadBundle, shelves } from './data';
import { InterestsAndFound, ProfileStep } from './Onboarding';
import { Player } from './Player';
import { Home, Nav, TopicPage, storiesOf } from './Screens';
import { NewTopicSheet, ProfileSheet, SettingsSheet, StorySheet } from './Sheets';
import { Topic, blankProfile, isNew, useProfiles } from './state';
import { Tree } from './Tree';
import { setHueOrder } from './ui';

type Screen = { name: 'home' } | { name: 'topic'; id: string; leaf?: string } | { name: 'tree' };
type SheetState = null | { kind: 'settings'; id: string } | { kind: 'new' } | { kind: 'profile' } | { kind: 'story'; story: Story };
interface PlayerState { topic: Topic; queue: Story[]; index: number }
type Layer = 'screen' | 'sheet' | 'player';

const PAGE = 50;

export default function App() {
  const [bundle, setBundle] = useState<Bundle | null>(null);
  const [error, setError] = useState('');
  const { names, profile, choose, signOut, update } = useProfiles();
  const [screens, setScreens] = useState<Screen[]>([{ name: 'home' }]);
  const [sheet, setSheet] = useState<SheetState>(null);
  const [player, setPlayer] = useState<PlayerState | null>(null);
  const [shown, setShown] = useState(PAGE);
  const [toast, setToast] = useState('');

  useEffect(() => {
    loadBundle()
      .then((b) => { setHueOrder(shelves(b).map((s) => s.slug)); setBundle(b); })
      .catch((e) => setError(String(e.message || e)));
  }, []);
  const catalog = useMemo(() => (bundle ? buildCatalog(bundle) : new Map()), [bundle]);

  /* Back climbs one level, and the phone's own back gesture is the same path:
     every layer opened pushes one history entry, and popping one closes the
     top layer — player, then sheet, then screen. */
  const layers = useRef<Layer[]>([]);
  const ignorePops = useRef(0);
  const open = useCallback((layer: Layer) => { layers.current.push(layer); history.pushState({ trib: layers.current.length }, ''); }, []);
  const applyClose = useCallback((top: Layer | undefined) => {
    if (top === 'player') setPlayer(null);
    else if (top === 'sheet') setSheet(null);
    else if (top === 'screen') { setScreens((s) => (s.length > 1 ? s.slice(0, -1) : s)); setShown(PAGE); }
  }, []);
  useEffect(() => {
    const onPop = () => {
      // A pop we caused ourselves (back() below) has already been applied.
      if (ignorePops.current > 0) { ignorePops.current -= 1; return; }
      applyClose(layers.current.pop());
    };
    window.addEventListener('popstate', onPop);
    return () => window.removeEventListener('popstate', onPop);
  }, [applyClose]);
  /* Close `n` layers now, then step history back by the same amount in one go,
     so nothing waits on an asynchronous popstate. */
  const back = useCallback((n = 1) => {
    const k = Math.min(n, layers.current.length);
    if (!k) return;
    for (let i = 0; i < k; i += 1) applyClose(layers.current.pop());
    ignorePops.current += 1;
    history.go(-k);
  }, [applyClose]);
  /* Turn the top layer into another without touching history: a sheet that
     leads into a topic, the player that leads into a story. */
  const swapTop = (layer: Layer) => { layers.current[layers.current.length - 1] = layer; };
  const resetNav = () => {
    const k = layers.current.length;
    layers.current = [];
    if (k) { ignorePops.current += 1; history.go(-k); }
    setSheet(null); setPlayer(null); setScreens([{ name: 'home' }]);
  };

  const flash = (msg: string) => { setToast(msg); window.setTimeout(() => setToast(''), 1800); };
  const markSeen = useCallback((s: Story) =>
    update((p) => (p.seen.includes(s.story_id) ? p : { ...p, seen: [...p.seen, s.story_id] })), [update]);

  const screen = screens[screens.length - 1];
  const topicById = (id: string) => profile?.topics.find((t) => t.id === id);
  const saveTopic = (t: Topic) => update((p) => ({ ...p, topics: p.topics.map((x) => (x.id === t.id ? t : x)) }));

  const nav: Nav = {
    openTopic: (id, leaf) => {
      if (sheet) { swapTop('screen'); setSheet(null); } else open('screen');
      setScreens((s) => [...s, { name: 'topic', id, leaf }]); setShown(PAGE); window.scrollTo(0, 0);
    },
    openStory: (story) => { markSeen(story); setSheet({ kind: 'story', story }); open('sheet'); },
    play: (topic, leaf) => {
      if (!bundle || !profile) return;
      const list = storiesOf(bundle, topic, leaf);
      const fresh = list.filter((s) => isNew(profile, s)).reverse(); // oldest first, so they read in order
      const queue = fresh.length ? fresh : list.slice(0, 10);
      if (!queue.length) return;
      setPlayer({ topic, queue, index: 0 }); open('player');
    },
    openTree: () => { setScreens((s) => [...s, { name: 'tree' }]); open('screen'); window.scrollTo(0, 0); },
    openProfile: () => { setSheet({ kind: 'profile' }); open('sheet'); },
    openSettings: (topic) => { setSheet({ kind: 'settings', id: topic.id }); open('sheet'); },
    newTopic: () => { setSheet({ kind: 'new' }); open('sheet'); },
    back: () => back(),
    setLayout: (layout) => update((p) => ({ ...p, layout })),
  };

  if (error) return <div className="app"><div className="empty big">{error}<br /><button className="btn" onClick={() => location.reload()}>Try again</button></div></div>;
  if (!profile) return <div className="app"><ProfileStep names={names} onChoose={choose} /></div>;
  if (!bundle) return <div className="app"><div className="empty big">Loading your news…</div></div>;

  if (!profile.onboarded) {
    return (
      <div className="app">
        <InterestsAndFound bundle={bundle} catalog={catalog} profile={profile}
          onDone={(topics) => { update((p) => ({ ...p, topics, onboarded: true })); window.scrollTo(0, 0); }} />
      </div>
    );
  }

  const currentTopic = screen.name === 'topic' ? topicById(screen.id) : undefined;
  const settingsTopic = sheet?.kind === 'settings' ? topicById(sheet.id) : undefined;

  return (
    <div className="app">
      {screen.name === 'tree'
        ? <Tree bundle={bundle} profile={profile} onBack={() => back()} onOpen={nav.openTopic} />
        : currentTopic
          ? <TopicPage bundle={bundle} profile={profile} topic={currentTopic} leaf={screen.name === 'topic' ? screen.leaf : undefined}
              nav={nav} shown={shown} more={() => setShown((n) => n + PAGE)} />
          : <Home bundle={bundle} profile={profile} nav={nav} shown={shown} more={() => setShown((n) => n + PAGE)} />}

      {bundle.status.broken_sources.length > 0 && (
        <p className="health">{bundle.status.broken_sources.length} source{bundle.status.broken_sources.length > 1 ? 's' : ''} not responding: {bundle.status.broken_sources.map((b) => b.name).join(', ')}</p>
      )}

      {sheet?.kind === 'story' && <StorySheet story={sheet.story} onClose={() => back()} />}
      {settingsTopic && (
        <SettingsSheet topic={settingsTopic} catalog={catalog} onClose={() => back()}
          onChange={saveTopic}
          onDelete={() => {
            update((p) => ({ ...p, topics: p.topics.filter((t) => t.id !== settingsTopic.id) }));
            back(screen.name === 'topic' ? 2 : 1); flash('Topic removed');
          }} />
      )}
      {sheet?.kind === 'new' && (
        <NewTopicSheet bundle={bundle} catalog={catalog} profile={profile} onClose={() => back()}
          onCreate={(t) => { update((p) => ({ ...p, topics: [...p.topics, t] })); nav.openTopic(t.id); flash('Topic created'); }} />
      )}
      {sheet?.kind === 'profile' && (
        <ProfileSheet profile={profile} onClose={() => back()}
          onTopic={(id) => nav.openTopic(id)}
          onSwitch={() => { resetNav(); signOut(); }}
          onReset={() => { resetNav(); update(() => blankProfile(profile.name)); }} />
      )}
      {player && (
        <Player topic={player.topic} queue={player.queue} index={player.index} onSeen={markSeen}
          onClose={() => back()}
          onRead={(s) => { swapTop('sheet'); setPlayer(null); markSeen(s); setSheet({ kind: 'story', story: s }); }}
          onStep={(d) => {
            const next = player.index + d;
            if (next >= player.queue.length) { back(); flash("You're all caught up"); }
            else setPlayer({ ...player, index: Math.max(0, next) });
          }} />
      )}
      {toast && <div className="toast" role="status">{toast}</div>}
    </div>
  );
}
