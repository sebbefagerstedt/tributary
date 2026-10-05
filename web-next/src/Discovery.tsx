/* Real discovery, only when the backend is there (NEXT.md step 2): a subject or
   a pasted site goes to /api/next/discover, and what comes back is shown in the
   same "Here is what we found" card as everything else. */

import { useEffect, useState } from 'react';
import { Source } from './data';
import { Candidate, Discovery, remote } from './remote';
import { SourceSpec } from './state';
import { FoundCard } from './ui';

export const slugOf = (text: string) =>
  text.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 60) || 'topic';

export const asSource = (c: Candidate): Source => ({ name: c.name, week: c.week, latest: c.latest, places: new Map() });
/* A source the server does not know yet travels whole, so it can be added. */
export const specsOf = (cs: Candidate[]): Record<string, SourceSpec> =>
  Object.fromEntries(cs.filter((c) => !c.known && c.url).map((c) => [c.name, { name: c.name, url: c.url!, kind: c.kind }]));

export function useDiscovery(query: string | null) {
  const [state, setState] = useState<{ loading: boolean; result: Discovery | null; error: string }>(
    { loading: false, result: null, error: '' });
  useEffect(() => {
    if (!query || query.trim().length < 2) { setState({ loading: false, result: null, error: '' }); return; }
    let live = true;
    setState({ loading: true, result: null, error: '' });
    remote.discover(query.trim())
      .then((result) => { if (live) setState({ loading: false, result, error: '' }); })
      .catch((e) => { if (live) setState({ loading: false, result: null, error: (e as Error).message }); });
    return () => { live = false; };
  }, [query]);
  return state;
}

/* One subject or site: what discovery found for it, all ticked to start with. */
export function DiscoveredCard({ query, chosen, setChosen, onFound }: {
  query: string; chosen: string[] | undefined;
  setChosen: (next: string[]) => void;
  onFound: (all: string[], specs: Record<string, SourceSpec>, title?: string) => void;
}) {
  const { loading, result, error } = useDiscovery(query);
  useEffect(() => {
    if (result && chosen === undefined) {
      onFound(result.sources.map((s) => s.name), specsOf(result.sources),
        result.kind === 'site' ? result.sources[0]?.name : undefined);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [result]);
  if (loading) return <div className="found"><div className="found-head"><div className="grow"><h3>{query}</h3><small>Searching…</small></div></div></div>;
  if (error) return <div className="found"><div className="found-head"><div className="grow"><h3>{query}</h3><small className="warn">{error}</small></div></div></div>;
  if (!result) return null;
  return (
    <>
      <FoundCard id={slugOf(query)} name={query} sources={result.sources.map(asSource)}
        chosen={chosen || []} setChosen={setChosen} />
      {result.note && <p className="hint discovery-note">{result.note}</p>}
    </>
  );
}
