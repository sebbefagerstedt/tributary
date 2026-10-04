/* The first run: a name, what you care about, what we found, then news. A
   device with nothing stored is a new reader, so this is testable without
   accounts — a private window starts it again. */

import { FormEvent, useMemo, useState } from 'react';
import { Bundle, Source, shelves, sourcesForShelf } from './data';
import { Profile, Topic } from './state';
import { FoundCard, hueOf } from './ui';

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

export function InterestsAndFound({ bundle, catalog, profile, onDone }: {
  bundle: Bundle; catalog: Map<string, Source>; profile: Profile; onDone: (topics: Topic[]) => void;
}) {
  const subjects = useMemo(() => shelves(bundle), [bundle]);
  const [picks, setPicks] = useState<string[]>([]);
  const [step, setStep] = useState<'interests' | 'found'>('interests');
  const [chosen, setChosen] = useState<Record<string, string[]>>({});

  const toFound = () => {
    const next: Record<string, string[]> = {};
    for (const id of picks) next[id] = sourcesForShelf(catalog, id).map((s) => s.name);
    setChosen(next);
    setStep('found');
    window.scrollTo(0, 0);
  };
  const finish = () => onDone(picks.map((id) => ({
    id, name: subjects.find((s) => s.slug === id)!.name, sources: chosen[id] || [], muted: [],
  })));

  if (step === 'interests') {
    return (
      <>
        <div className="stepper"><i className="on" /><i className="on" /><i /></div>
        <div className="hero"><h1>What do you care about, {profile.name}?</h1>
          <p>Pick a few. Each becomes a topic you can shape later.</p></div>
        <div className="interest-grid" style={{ marginTop: 14 }}>
          {subjects.map((s) => (
            <button key={s.slug} className="interest" aria-pressed={picks.includes(s.slug)}
              onClick={() => setPicks((p) => (p.includes(s.slug) ? p.filter((x) => x !== s.slug) : [...p, s.slug]))}>
              <span className="em" style={{ background: hueOf(s.slug) }}>{s.name[0]}</span>{s.name}
            </button>
          ))}
        </div>
        <p className="mock-note">Any subject you can name — searched on the web — arrives with the backend. For now these are the subjects Tributary already reads.</p>
        <div className="sticky-cta">
          <button className="btn primary wide" disabled={!picks.length} onClick={toFound}>
            {picks.length ? `Find sources for ${picks.length} topic${picks.length > 1 ? 's' : ''}` : 'Pick at least one'}
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
      </div>
      <div className="sticky-cta">
        <button className="btn ghost" onClick={() => setStep('interests')}>Back</button>
        <button className="btn primary wide" onClick={finish}>Show me my news</button>
      </div>
    </>
  );
}
