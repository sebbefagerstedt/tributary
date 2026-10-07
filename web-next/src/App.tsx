import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Bundle, Story, buildCatalog, loadBundle, nodeOf, sourcesFor } from './data';
import { InterestsAndFound, ProfileStep } from './Onboarding';
import { Player } from './Player';
import { Home, Nav, TopicPage, storiesOf } from './Screens';
import { NewTopicSheet, ProfileSheet, SettingsSheet, StorySheet } from './Sheets';
import { hasServer, remote } from './remote';
import { Topic, isNew, placeTopic, useProfiles } from './state';
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
  const [toast, setToast] = useState('');
  const flash = useCallback((msg: string, ms = 1800) => { setToast(msg); window.setTimeout(() => setToast(''), ms); }, []);
  /* Served by `trib serve`, the page keeps readers on the server and can search
     the web; on GitHub Pages nothing answers and it stays in this browser. */
  const [server, setServer] = useState<boolean | null>(null);
  useEffect(() => { hasServer().then(setServer); }, []);

  const reload = useCallback(() => loadBundle()
    .then((b) => {
      // Categories take the first colours, so eight of them never share one.
      setHueOrder([...b.spine.filter((s) => !s.parent), ...b.spine.filter((s) => s.parent)].map((s) => s.slug));
      setBundle(b);
    })
    .catch((e) => setError(String(e.message || e))), []);
  useEffect(() => { reload(); }, [reload]);

  /* A topic saved with sources the server had never read: run the pipeline
     once, so their news arrives now rather than at the next scheduled run. */
  const refreshing = useRef(false);
  const onNewSources = useCallback(async () => {
    if (refreshing.current) return;
    refreshing.current = true;
    flash('Fetching your new sources…', 4000);
    try {
      await remote.refresh();
      for (;;) {
        await new Promise((r) => window.setTimeout(r, 4000));
        const st = await remote.refreshStatus();
        if (!st.running) {
          await reload();
          flash(st.ok === false ? 'Some sources could not be fetched' : 'Your new sources are in', 2500);
          break;
        }
      }
    } catch (e) {
      flash(`Could not fetch: ${(e as Error).message}`, 3000);
    } finally {
      refreshing.current = false;
    }
  }, [flash, reload]);
  const onError = useCallback((msg: string) => flash(msg, 3000), [flash]);
  const { names, profile, choose, signOut, update, reset } = useProfiles(server, onError, onNewSources);
  const [screens, setScreens] = useState<Screen[]>([{ name: 'home' }]);
  const [sheet, setSheet] = useState<SheetState>(null);
  const [player, setPlayer] = useState<PlayerState | null>(null);
  const [shown, setShown] = useState(PAGE);
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

  const markSeen = useCallback((s: Story) =>
    update((p) => (p.seen.includes(s.story_id) ? p : { ...p, seen: [...p.seen, s.story_id] })), [update]);

  const screen = screens[screens.length - 1];
  const topicById = (id: string) => profile?.topics.find((t) => t.id === id);
  /* A page opens on a topic you follow, or on any place in the tree, followed
     or not: you look before you follow, and can follow a subtopic alone. */
  const pageTopic = (id: string) => {
    const mine = topicById(id);
    if (mine || !bundle) return mine;
    const node = nodeOf(bundle, id);
    return node ? placeTopic(id, node.name, sourcesFor(catalog, id).map((s) => s.name)) : undefined;
  };
  const saveTopic = (t: Topic) => update((p) => ({ ...p, topics: p.topics.map((x) => (x.id === t.id ? t : x)) }));

  const nav: Nav = {
    openPlace: (slug) => {
      const mine = profile?.topics.find((t) => t.spine === slug);
      nav.openTopic(mine ? mine.id : slug);
    },
    follow: (slug) => {
      const node = bundle && nodeOf(bundle, slug);
      if (!node || profile?.topics.some((t) => t.spine === slug)) return;
      update((p) => ({ ...p, topics: [...p.topics, placeTopic(slug, node.name, sourcesFor(catalog, slug).map((s) => s.name))] }));
      flash(`Following ${node.name}`);
    },
    unfollow: (topic) => {
      update((p) => ({ ...p, topics: p.topics.filter((t) => t.id !== topic.id) }));
      flash(`Stopped following ${topic.name}`);
      // A topic of your own has no place in the tree to stay on.
      if (!topic.spine && screen.name === 'topic' && screen.id === topic.id) back();
    },
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
  if (server === null) return <div className="app"><div className="empty big">Loading…</div></div>;
  if (!profile) return <div className="app"><ProfileStep names={names} onChoose={choose} /></div>;
  if (!bundle) return <div className="app"><div className="empty big">Loading your news…</div></div>;

  if (!profile.onboarded) {
    return (
      <div className="app">
        <InterestsAndFound bundle={bundle} catalog={catalog} profile={profile} server={server}
          onDone={(topics) => { update((p) => ({ ...p, topics, onboarded: true })); window.scrollTo(0, 0); }} />
      </div>
    );
  }

  const currentTopic = screen.name === 'topic' ? pageTopic(screen.id) : undefined;
  const settingsTopic = sheet?.kind === 'settings' ? topicById(sheet.id) : undefined;

  return (
    <div className="app">
      {screen.name === 'tree'
        ? <Tree bundle={bundle} profile={profile} onBack={() => back()} onOpen={nav.openTopic} onAdd={nav.follow} />
        : currentTopic
          ? <TopicPage bundle={bundle} profile={profile} topic={currentTopic} leaf={screen.name === 'topic' ? screen.leaf : undefined}
              nav={nav} shown={shown} more={() => setShown((n) => n + PAGE)} />
          : <Home bundle={bundle} profile={profile} nav={nav} shown={shown} more={() => setShown((n) => n + PAGE)} />}

      {bundle.status.broken_sources.length > 0 && (
        <p className="health">{bundle.status.broken_sources.length} source{bundle.status.broken_sources.length > 1 ? 's' : ''} not responding: {bundle.status.broken_sources.map((b) => b.name).join(', ')}</p>
      )}

      {sheet?.kind === 'story' && (
        <StorySheet story={sheet.story} bundle={bundle} profile={profile} catalog={catalog} onClose={() => back()}
          onOpenTopic={(id) => nav.openTopic(id)}
          onFollow={(t) => { update((p) => ({ ...p, topics: [...p.topics, t] })); flash(`Following ${t.name}`); }} />
      )}
      {settingsTopic && (
        <SettingsSheet topic={settingsTopic} catalog={catalog} server={server} onClose={() => back()}
          onChange={saveTopic}
          onDelete={() => {
            update((p) => ({ ...p, topics: p.topics.filter((t) => t.id !== settingsTopic.id) }));
            back(screen.name === 'topic' ? 2 : 1); flash('Topic removed');
          }} />
      )}
      {sheet?.kind === 'new' && (
        <NewTopicSheet bundle={bundle} catalog={catalog} profile={profile} server={server} onClose={() => back()}
          onCreate={(t) => { update((p) => ({ ...p, topics: [...p.topics, t] })); nav.openTopic(t.id); flash('Topic created'); }} />
      )}
      {sheet?.kind === 'profile' && (
        <ProfileSheet profile={profile} server={server} onClose={() => back()}
          onTopic={(id) => nav.openTopic(id)}
          onSwitch={() => { resetNav(); signOut(); }}
          onReset={() => { resetNav(); reset(); }} />
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
