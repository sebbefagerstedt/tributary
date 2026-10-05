/* The first run: a name, what you care about, what we found, then news. A
   device with nothing stored is a new reader, so this is testable without
   accounts — a private window starts it again. With the backend there you can
   also type any subject or paste a site, and it is searched for real. */

import { FormEvent, useMemo, useState } from 'react';
import { Bundle, STARTER_AREA, Source, shelves, sourcesForShelf } from './data';
import { DiscoveredCard, slugOf } from './Discovery';
import { Profile, SourceSpec, Topic } from './state';
import { FoundCard, StarterList } from './ui';

export function ProfileStep({ names, onChoose }: { names: string[]; onChoose: (n: string) => void }) {
  const [name, setName] = useState('');
  const submit = (e: FormEvent) => { e.preventDefault(); if (name.trim()) onChoose(name); };
  return (
    <>
      <div className="stepper"><i className="on" /><i /><i /></div>
      <div className="hero">
        <span className="eyebrow">Welcome to</span>
        <h1>Tributary<span style={{ color: 'var(--accent)' }}>.</span></h1>
        <p>Your own news, from sources you choose. Start with a name — no password.</p>
      </div>
      <form className="stack" style={{ marginTop: 18 }} onSubmit={submit}>
        <label className="eyebrow" htmlFor="name">Your name</label>
        <input className="field" id="name" autoComplete="nickname" placeholder="e.g. Sebastian"
          value={name} onChange={(e) => setName(e.target.value)} />
        <button className="btn primary wide" type="submit">Continue</button>
      </form>
      {names.length > 0 && (
        <div className="section">
          <h3>Or continue as</h3>
          <div className="chips">{names.map((n) => <button key={n} className="chip" onClick={() => onChoose(n)}>{n}</button>)}</div>
        </div>
      )}
    </>
  );
}

export function InterestsAndFound({ bundle, catalog, profile, server, onDone }: {
  bundle: Bundle; catalog: Map<string, Source>; profile: Profile; server: boolean; onDone: (topics: Topic[]) => void;
}) {
  const subjects = useMemo(() => shelves(bundle), [bundle]);
  const [picks, setPicks] = useState<string[]>([]);
  const [own, setOwn] = useState<string[]>([]);       // subjects you typed
  const [typed, setTyped] = useState('');
  const [step, setStep] = useState<'interests' | 'found'>('interests');
  const [chosen, setChosen] = useState<Record<string, string[]>>({});
  const [specs, setSpecs] = useState<Record<string, Record<string, SourceSpec>>>({});
  const [titles, setTitles] = useState<Record<string, string>>({});
  const count = picks.length + own.length;

  const addOwn = (e: FormEvent) => {
    e.preventDefault();
    const q = typed.trim();
    if (q.length >= 2 && !own.includes(q)) setOwn([...own, q]);
    setTyped('');
  };
  const toFound = () => {
    setChosen((c) => {
      const next = { ...c };
      for (const id of picks) next[id] = next[id] || sourcesForShelf(catalog, id).map((s) => s.name);
      return next;
    });
    setStep('found');
    window.scrollTo(0, 0);
  };
  const finish = () => onDone([
    ...picks.map((id) => ({ id, name: subjects.find((s) => s.slug === id)!.name, spine: id, sources: chosen[id] || [], muted: [] })),
    ...own.map((q) => {
      const sources = chosen[`own:${q}`] || [];
      const found = Object.fromEntries(Object.entries(specs[`own:${q}`] || {}).filter(([n]) => sources.includes(n)));
      const name = titles[`own:${q}`] || q;
      return { id: slugOf(name), name, description: q, spine: null, sources, muted: [], found };
    }),
  ]);

  if (step === 'interests') {
    return (
      <>
        <div className="stepper"><i className="on" /><i className="on" /><i /></div>
        <div className="hero"><h1>What do you care about, {profile.name}?</h1>
          <p>Pick a few. Each becomes a topic you can shape later.</p></div>
        <div className="area"><b>{STARTER_AREA}</b><span>the subjects Tributary reads today</span></div>
        <StarterList subjects={subjects} picked={picks}
          onPick={(slug) => setPicks((p) => (p.includes(slug) ? p.filter((x) => x !== slug) : [...p, slug]))} />
        {server ? (
          <>
            <form className="row" style={{ marginTop: 12 }} onSubmit={addOwn}>
              <input className="field" id="own" placeholder="Or type your own — a subject, or paste a site"
                value={typed} onChange={(e) => setTyped(e.target.value)} style={{ flex: 1 }} />
              <button className="btn" type="submit">Add</button>
            </form>
            {own.length > 0 && (
              <div className="chips" style={{ marginTop: 10 }}>
                {own.map((q) => <button key={q} className="chip place" onClick={() => setOwn(own.filter((x) => x !== q))}>{q} ×</button>)}
              </div>
            )}
          </>
        ) : (
          <p className="mock-note">Subjects outside {STARTER_AREA}, with sources found on the web, come with the server.</p>
        )}
        <div className="sticky-cta">
          <button className="btn primary wide" disabled={!count} onClick={toFound}>
            {count ? `Find sources for ${count} topic${count > 1 ? 's' : ''}` : 'Pick at least one'}
          </button>
        </div>
      </>
    );
  }
  return (
    <>
      <div className="stepper"><i className="on" /><i className="on" /><i className="on" /></div>
      <div className="hero" style={{ paddingBottom: 4 }}><h1>Here's what we found</h1>
        <p>Sources for each topic. Keep them all, or pick a few — you can change this any time.</p></div>
      <div className="stack" style={{ marginTop: 12 }}>
        {picks.map((id) => (
          <FoundCard key={id} id={id} name={subjects.find((s) => s.slug === id)!.name}
            sources={sourcesForShelf(catalog, id)} chosen={chosen[id] || []}
            setChosen={(next) => setChosen((c) => ({ ...c, [id]: next }))} />
        ))}
        {own.map((q) => {
          const key = `own:${q}`;
          return (
            <DiscoveredCard key={key} query={q} chosen={chosen[key]}
              setChosen={(next) => setChosen((c) => ({ ...c, [key]: next }))}
              onFound={(all, found, title) => {
                setChosen((c) => ({ ...c, [key]: all }));
                setSpecs((s) => ({ ...s, [key]: found }));
                if (title) setTitles((t) => ({ ...t, [key]: title }));
              }} />
          );
        })}
      </div>
      <div className="sticky-cta">
        <button className="btn ghost" onClick={() => setStep('interests')}>Back</button>
        <button className="btn primary wide" onClick={finish}>Show me my news</button>
      </div>
    </>
  );
}
