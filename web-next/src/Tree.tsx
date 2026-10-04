/* Your tree as a graph: you in the middle, your topics around you, their
   subtopics and sources outside them. After the reference in
   docs/reference/tree-view-magnowlia.png, calmer: colour-coded nodes, curved
   links, room to breathe. Tapping a topic or subtopic opens it. */

import { useEffect, useRef } from 'react';
import { Bundle } from './data';
import { Profile } from './state';
import { ICON, hueOf } from './ui';
import { storiesOf } from './Screens';

interface Node { key: string; kind: 'topic' | 'sub' | 'src'; x: number; y: number; label: string; hue: string; topic: string; leaf?: string }
interface Edge { a: [number, number]; b: [number, number]; cls: string }

const W = 640, HT = 640, CX = W / 2, CY = HT / 2, R1 = 115, R2 = 210;
const SOURCES_SHOWN = 3;

export function Tree({ bundle, profile, onBack, onOpen }: {
  bundle: Bundle; profile: Profile; onBack: () => void; onOpen: (id: string, leaf?: string) => void;
}) {
  const wrap = useRef<HTMLDivElement>(null);
  // On a phone the graph is wider than the screen: start with you in the middle.
  useEffect(() => { const el = wrap.current; if (el) el.scrollLeft = (el.scrollWidth - el.clientWidth) / 2; }, []);
  const nodes: Node[] = [];
  const edges: Edge[] = [];
  const topics = profile.topics;
  const n = Math.max(topics.length, 1);
  topics.forEach((t, i) => {
    const a = -Math.PI / 2 + (i / n) * Math.PI * 2;
    const x = CX + Math.cos(a) * R1, y = CY + Math.sin(a) * R1;
    const hue = hueOf(t.id);
    nodes.push({ key: t.id, kind: 'topic', x, y, label: t.name, hue, topic: t.id });
    edges.push({ a: [CX, CY], b: [x, y], cls: '' });
    // Only subtopics that hold something of yours, then the busiest sources.
    const leaves = bundle.spine.filter((l) => l.parent === t.id && storiesOf(bundle, t, l.slug).length > 0);
    const outer = [
      ...leaves.map((l) => ({ kind: 'sub' as const, label: l.name, leaf: l.slug })),
      ...t.sources.slice(0, SOURCES_SHOWN).map((s) => ({ kind: 'src' as const, label: s, leaf: undefined })),
    ];
    const spread = Math.min(1.9, ((Math.PI * 2) / n) * 0.7);
    outer.forEach((o, j) => {
      const aa = a + (outer.length > 1 ? (j / (outer.length - 1) - 0.5) * spread : 0);
      const rr = R2 + (j % 2) * 50;
      const ox = CX + Math.cos(aa) * rr, oy = CY + Math.sin(aa) * rr;
      nodes.push({ key: `${t.id}:${o.kind}:${o.label}`, kind: o.kind, x: ox, y: oy, label: o.label, hue, topic: t.id, leaf: o.leaf });
      edges.push({ a: [x, y], b: [ox, oy], cls: o.kind === 'src' ? 'src' : '' });
    });
  });

  const curve = (e: Edge) => {
    const mx = (e.a[0] + e.b[0]) / 2, my = (e.a[1] + e.b[1]) / 2;
    const dx = e.b[1] - e.a[1], dy = e.a[0] - e.b[0];
    const k = 14 / (Math.hypot(dx, dy) || 1);
    return `M${e.a[0].toFixed(1)},${e.a[1].toFixed(1)} Q${(mx + dx * k).toFixed(1)},${(my + dy * k).toFixed(1)} ${e.b[0].toFixed(1)},${e.b[1].toFixed(1)}`;
  };
  const box = (nd: Node) => {
    const fs = nd.kind === 'topic' ? 13 : 10.5;
    const label = nd.label.length > 22 ? nd.label.slice(0, 21) + '…' : nd.label;
    const w = Math.min(label.length * fs * 0.58 + 18, 150), h = nd.kind === 'topic' ? 30 : 22;
    const open = nd.kind !== 'src' ? () => onOpen(nd.topic, nd.leaf) : undefined;
    return (
      <g key={nd.key} className={`node ${open ? 'tappable' : ''}`} onClick={open} tabIndex={open ? 0 : -1}
        onKeyDown={(e) => { if (open && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); open(); } }}>
        <rect x={nd.x - w / 2} y={nd.y - h / 2} width={w} height={h} rx={h / 2}
          fill={nd.kind === 'src' ? 'var(--surface-2)' : nd.hue} fillOpacity={nd.kind === 'sub' ? 0.55 : 1}
          stroke={nd.kind === 'src' ? 'var(--line)' : 'none'} />
        <text x={nd.x} y={nd.y + fs * 0.36} textAnchor="middle" fontSize={fs} fill={nd.kind === 'src' ? 'var(--fg)' : '#fff'}>{label}</text>
      </g>
    );
  };
  return (
    <>
      <div className="bar">
        <button className="icon-btn" onClick={onBack} aria-label="Back">{ICON.back}</button>
        <div className="grow"><div className="crumbs">{profile.name}</div><div className="title-sm">Your tree</div></div>
      </div>
      <div className="tree-wrap" ref={wrap}>
        <svg viewBox={`0 0 ${W} ${HT}`} role="img" aria-label="Your topics, subtopics and sources as a graph">
          {edges.map((e, i) => <path key={i} className={`edge ${e.cls}`} d={curve(e)} />)}
          <circle cx={CX} cy={CY} r={26} fill="var(--fg)" />
          <text x={CX} y={CY + 5} textAnchor="middle" fontSize={14} fontWeight={800} fill="var(--bg)">{profile.name[0].toUpperCase()}</text>
          {nodes.filter((nd) => nd.kind !== 'topic').map(box)}
          {nodes.filter((nd) => nd.kind === 'topic').map(box)}
        </svg>
      </div>
      <div className="legend">
        <span><i style={{ background: 'var(--accent)' }} />Topic</span>
        <span><i style={{ background: 'var(--accent)', opacity: 0.55 }} />Subtopic</span>
        <span><i style={{ background: 'var(--surface-2)', border: '1px solid var(--line)' }} />Source</span>
      </div>
      <p className="mock-note">Swipe sideways to explore; tap a topic or subtopic to open it.</p>
    </>
  );
}
