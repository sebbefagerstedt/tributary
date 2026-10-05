/* Your tree: AI at the top, its topics, their subtopics indented under them,
   your own topics after -- and dashed arcs between topics whose stories are
   alike (graph.ts). After the reference in
   docs/reference/tree-view-magnowlia.png, but shaped for a phone: an outline
   you scroll down, so no label ever sits on another. Filters keep it calm;
   tapping a node focuses it -- its links light up, the rest fades, and a panel
   says what it is closest to, inside your topics or anywhere in AI. */

import { useEffect, useMemo, useRef, useState } from 'react';
import { Bundle } from './data';
import { GEdge, GNode, Options, buildGraph, closest, focusEdges } from './graph';
import { Profile } from './state';
import { ICON, hueOf } from './ui';

const KIND_NAME = { area: 'Subject', shelf: 'Topic', leaf: 'Subtopic', own: 'Your topic', src: 'Source' } as const;

/* Where a node's line leaves it for its children, and where one arrives. */
const outOf = (n: GNode): [number, number] => (n.kind === 'area' ? [n.x + 22, n.y + 20] : [n.x + 14, n.y + n.h / 2 - 8]);
const treePath = (p: GNode, c: GNode) => {
  const [sx, sy] = outOf(p);
  const r = 9;
  return `M${sx},${sy} L${sx},${c.y - r} Q${sx},${c.y} ${sx + r},${c.y} L${c.x},${c.y}`;
};
const arcPath = (a: GNode, b: GNode, width: number) => {
  const ax = a.x + a.w, bx = b.x + b.w;
  const gx = Math.min(width - 6, Math.max(ax, bx) + 22 + Math.abs(b.y - a.y) * 0.1);
  return `M${ax},${a.y} C${gx},${a.y} ${gx},${b.y} ${bx},${b.y}`;
};

export function Tree({ bundle, profile, onBack, onOpen, onAdd }: {
  bundle: Bundle; profile: Profile; onBack: () => void;
  onOpen: (id: string, leaf?: string) => void; onAdd: (shelf: string) => void;
}) {
  const [opts, setOpts] = useState<Options>({ scope: profile.topics.length ? 'mine' : 'all', related: true, sources: false });
  const [sel, setSel] = useState<string | null>(null);
  const g = useMemo(() => buildGraph(bundle, profile, opts), [bundle, profile, opts]);
  // "Closest to" looks across all of AI, whatever is drawn.
  const everything = useMemo(() => buildGraph(bundle, profile, { scope: 'all', related: false, sources: false }), [bundle, profile]);
  const byKey = useMemo(() => new Map(g.nodes.map((n) => [n.key, n])), [g.nodes]);
  const wrap = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(340);
  useEffect(() => {
    const el = wrap.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setWidth(el.clientWidth));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  useEffect(() => { if (sel && !byKey.has(sel)) setSel(null); }, [byKey, sel]);

  const selected = sel ? byKey.get(sel) : undefined;
  const rel: GEdge[] = selected ? focusEdges(selected, g.nodes, g.vectors) : g.overview;
  const lit = useMemo(() => {
    if (!sel) return null;
    const s = new Set([sel]);
    for (const e of [...g.edges, ...rel]) { if (e.a === sel) s.add(e.b); if (e.b === sel) s.add(e.a); }
    return s;
  }, [sel, g.edges, rel]);
  const nearAll = selected ? closest(everything.nodes.find((n) => n.key === selected.key) ?? selected, everything.nodes, everything.vectors, 4) : [];

  const hue = (n: GNode) => (n.kind === 'own' ? hueOf(n.topicId!) : hueOf(n.shelf || n.key));
  const pick = (key: string) => {
    if (!byKey.has(key)) setOpts((o) => ({ ...o, scope: 'all' })); // it lives outside your topics
    setSel(key);
    window.setTimeout(() => {
      const svg = wrap.current?.querySelector('svg');
      const node = svg?.querySelector(`[data-key="${CSS.escape(key)}"]`);
      node?.scrollIntoView({ block: 'center', behavior: 'smooth' });
    }, 30);
  };

  const draw = (n: GNode) => {
    const dim = lit && !lit.has(n.key);
    const focus = n.key === sel;
    const tap = () => (focus ? setSel(null) : setSel(n.key));
    const props = {
      key: n.key, 'data-key': n.key, className: `node tappable${dim ? ' dim' : ''}${focus ? ' focus' : ''}`,
      onClick: tap, tabIndex: 0, role: 'button', 'aria-label': `${KIND_NAME[n.kind]}: ${n.label}`,
      onKeyDown: (e: React.KeyboardEvent) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); tap(); } },
    };
    const c = hue(n);
    const text = n.label.length > 26 ? n.label.slice(0, 25) + '…' : n.label;
    const top = n.y - (n.kind === 'leaf' || n.kind === 'src' ? 12 : 15), h = n.kind === 'leaf' || n.kind === 'src' ? 24 : 30;
    if (n.kind === 'area') {
      return <g {...props}><circle cx={n.x + 22} cy={n.y} r={20} fill="var(--fg)" />
        <text x={n.x + 22} y={n.y + 5} textAnchor="middle" fontSize={14} fontWeight={800} fill="var(--bg)">{n.label}</text>
        <text x={n.x + 52} y={n.y + 5} fontSize={13} fill="var(--muted)">the subjects Tributary reads</text></g>;
    }
    if (n.kind === 'shelf' || n.kind === 'own') {
      // Followed: solid in its colour. The rest of AI: outlined, to look at.
      const solid = n.followed;
      return <g {...props}>
        <rect x={n.x} y={top} width={n.w} height={h} rx={h / 2} fill={solid ? c : 'var(--surface)'} stroke={c} strokeWidth={solid ? 0 : 1.8} />
        <text x={n.x + n.w / 2} y={n.y + 4.6} textAnchor="middle" fontSize={13} fontWeight={700} fill={solid ? '#fff' : c}>{text}</text>
      </g>;
    }
    if (n.kind === 'leaf') {
      return <g {...props}>
        <rect x={n.x} y={top} width={n.w} height={h} rx={h / 2} fill="var(--surface)" stroke={c} strokeOpacity={n.followed ? 0.8 : 0.35} strokeWidth={1.4} />
        <circle cx={n.x + 12} cy={n.y} r={4} fill={c} />
        <text x={n.x + 21} y={n.y + 4} fontSize={11.5} fontWeight={600} fill="var(--fg)">{text}</text>
      </g>;
    }
    return <g {...props}>
      <rect x={n.x} y={top} width={n.w} height={h} rx={7} fill="var(--surface-2)" />
      <text x={n.x + 12} y={n.y + 4} fontSize={11} fill="var(--muted)">{text}</text>
    </g>;
  };

  const shelfOfSel = selected?.kind === 'leaf' ? byKey.get(`shelf:${selected.shelf}`) : undefined;
  return (
    <>
      <div className="bar">
        <button className="icon-btn" onClick={onBack} aria-label="Back">{ICON.back}</button>
        <div className="grow"><div className="crumbs">{profile.name}</div><div className="title-sm">Your tree</div></div>
      </div>
      <div className="tree-filters">
        <div className="switch" role="group" aria-label="Show">
          <button aria-pressed={opts.scope === 'mine'} onClick={() => setOpts((o) => ({ ...o, scope: 'mine' }))}>Yours</button>
          <button aria-pressed={opts.scope === 'all'} onClick={() => setOpts((o) => ({ ...o, scope: 'all' }))}>All of AI</button>
        </div>
        <button className="chip" aria-pressed={opts.related} onClick={() => setOpts((o) => ({ ...o, related: !o.related }))}>Related</button>
        <button className="chip" aria-pressed={opts.sources} onClick={() => setOpts((o) => ({ ...o, sources: !o.sources }))}>Sources</button>
      </div>
      <div className={`tree-wrap${selected ? ' with-panel' : ''}`} ref={wrap} onClick={(e) => { if ((e.target as Element).tagName === 'svg') setSel(null); }}>
        {g.nodes.length === 0
          ? <p className="hint" style={{ padding: 16 }}>You have no topics yet. Show all of AI to look around.</p>
          : (
            <svg width={width} height={g.height} viewBox={`0 0 ${width} ${g.height}`} role="img" aria-label="Your topics and how they relate">
              {g.edges.map((e) => {
                const a = byKey.get(e.a), b = byKey.get(e.b);
                if (!a || !b) return null;
                const on = !!sel && (e.a === sel || e.b === sel);
                return <path key={`${e.a}>${e.b}`} className={`edge ${e.kind}${lit && !on ? ' dim' : ''}${on ? ' on' : ''}`} d={treePath(a, b)} />;
              })}
              {rel.map((e) => {
                const a = byKey.get(e.a), b = byKey.get(e.b);
                if (!a || !b) return null;
                return <path key={`rel:${e.a}|${e.b}`} className={`edge rel${sel ? ' on' : ''}`} d={arcPath(a, b, width)} />;
              })}
              {g.nodes.map(draw)}
            </svg>
          )}
      </div>
      <div className="tree-panel">
        {selected ? (
          <>
            <button className="x panel-x" onClick={() => setSel(null)} aria-label="Clear">✕</button>
            <div>
              <div className="eyebrow">{KIND_NAME[selected.kind]}{shelfOfSel ? ` in ${shelfOfSel.label}` : selected.kind === 'shelf' ? ' in AI' : ''}</div>
              <h3>{selected.label}</h3>
            </div>
            {nearAll.length > 0 && (
              <div className="chips">
                <span className="sub">Closest to</span>
                {nearAll.map(({ node }) => (
                  <button key={node.key} className="chip" onClick={() => pick(node.key)}>
                    <i className="dot-hue" style={{ background: hue(node) }} />{node.label}
                  </button>
                ))}
              </div>
            )}
            {selected.topicId && selected.kind !== 'src' && (
              <button className="btn primary" onClick={() => onOpen(selected.topicId!, selected.kind === 'leaf' ? selected.slug : undefined)}>Open</button>
            )}
            {!selected.topicId && selected.shelf && (
              <button className="btn primary" onClick={() => onAdd(selected.shelf!)}>
                Add {selected.kind === 'leaf' ? shelfOfSel?.label : selected.label} to your topics
              </button>
            )}
          </>
        ) : (
          <p className="hint">Tap a topic to see what it is closest to. Dashed arcs join topics whose stories are alike.</p>
        )}
      </div>
    </>
  );
}
