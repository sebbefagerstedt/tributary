/* Your tree as an ontology graph (graph.ts): AI at the hub, its topics, their
   subtopics, your own topics and, if asked, the sources feeding them, with
   dashed links between topics whose stories are alike. After the reference in
   docs/reference/tree-view-magnowlia.png, calmer: a canvas you drag and pinch
   like a map, where names keep their size and only the distances zoom, so a
   label is always readable; subtopic names appear as you zoom in. Filters keep
   it from becoming a hairball, and tapping a node focuses it -- its links
   light up, the rest fades, and a panel says what it is closest to. */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Bundle } from './data';
import { GEdge, GNode, Options, buildGraph, closest, focusEdges } from './graph';
import { Profile } from './state';
import { ICON, hueOf } from './ui';

const kindName = (n: GNode) => (n.kind === 'area' ? 'Everything' : n.kind === 'own' ? 'Your topic' : n.kind === 'src' ? 'Source'
  : n.depth === 1 ? 'Category' : n.kind === 'branch' ? 'Topic' : 'Subtopic');
const MIN_ZOOM = 0.25, MAX_ZOOM = 2.5;
// A name is drawn only where it does not cover another, most important first;
// the rest are dots until you zoom in. This is how a map declutters.
// Categories first, then topics deeper in, then the smallest, then sources.
const rank = (n: GNode) => (n.kind === 'own' || n.mine || n.depth === 1 ? 1 : n.kind === 'branch' ? 2 : n.kind === 'leaf' ? 3 : 4);
const alwaysNamed = (n: GNode) => n.kind === 'own' || !!n.mine || (n.kind === 'branch' && n.depth === 1);
// Names shrink a little as you zoom out, as a map's do, and never below this.
const labelScale = (s: number) => Math.min(1, Math.max(0.68, 0.45 + s * 0.55));

interface View { s: number; tx: number; ty: number }

export function Tree({ bundle, profile, onBack, onOpen, onAdd }: {
  bundle: Bundle; profile: Profile; onBack: () => void;
  onOpen: (id: string, leaf?: string) => void; onAdd: (slug: string) => void;
}) {
  const [opts, setOpts] = useState<Options>({ scope: profile.topics.length ? 'mine' : 'all', related: true, sources: false });
  const [sel, setSel] = useState<string | null>(null);
  const g = useMemo(() => buildGraph(bundle, profile, opts), [bundle, profile, opts]);
  // "Closest to" looks across everything, whatever is drawn.
  const everything = useMemo(() => buildGraph(bundle, profile, { scope: 'all', related: false, sources: false }), [bundle, profile]);
  const byKey = useMemo(() => new Map(g.nodes.map((n) => [n.key, n])), [g.nodes]);

  const box = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ w: 340, h: 520 });
  const [view, setView] = useState<View>({ s: 1, tx: 170, ty: 260 });
  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setSize({ w: el.clientWidth, h: el.clientHeight }));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  /* Fit the topics on screen, never larger than life. Their subtopics and
     sources may run off the edge -- framing every dot left the names too small
     to place. */
  const fit = useCallback((whole = false) => {
    if (!g.nodes.length) return;
    const tops = g.nodes.filter((n) => n.kind === 'area' || alwaysNamed(n));
    // Names keep their size while distances zoom, so fit the centres and
    // leave a margin of the widest name.
    const set = whole || !tops.length ? g.nodes : tops;
    const xs = set.map((n) => n.x), ys = set.map((n) => n.y);
    const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys);
    const padW = Math.max(...set.map((n) => n.w)) * 0.7 + 24, padH = Math.max(...set.map((n) => n.h)) + 40;
    const fits = Math.min(1, (size.w - padW) / Math.max(x1 - x0, 1), (size.h - padH) / Math.max(y1 - y0, 1));
    // But never so far out that two topic names touch, at the size names
    // have at that zoom: the least zoom that keeps them apart is the floor.
    const apartAt = (z: number) => {
      const k = labelScale(z);
      for (let i = 0; i < tops.length; i += 1) {
        for (let j = i + 1; j < tops.length; j += 1) {
          const p = tops[i], q = tops[j];
          if (Math.abs(p.x - q.x) * z < ((p.w + q.w) / 2) * k + 4 && Math.abs(p.y - q.y) * z < ((p.h + q.h) / 2) * k + 2) return false;
        }
      }
      return true;
    };
    if (whole) {
      const s = Math.max(MIN_ZOOM, Math.min(1, fits));
      setView({ s, tx: size.w / 2 - ((x0 + x1) / 2) * s, ty: size.h / 2 - ((y0 + y1) / 2) * s });
      return;
    }
    let lo = MIN_ZOOM, hi = 1;
    if (apartAt(lo)) hi = lo;
    for (let i = 0; i < 18 && hi - lo > 0.005; i += 1) { const mid = (lo + hi) / 2; if (apartAt(mid)) hi = mid; else lo = mid; }
    const apart = hi;
    // The fit button frames everything; the opening view keeps names readable.
    const s = Math.max(MIN_ZOOM, Math.min(1, whole ? fits : Math.max(fits, apart)));
    setView({ s, tx: size.w / 2 - ((x0 + x1) / 2) * s, ty: size.h / 2 - ((y0 + y1) / 2) * s });
  }, [g.nodes, size]);
  useEffect(() => { fit(false); }, [fit]);
  useEffect(() => { if (sel && !byKey.has(sel)) setSel(null); }, [byKey, sel]);

  const zoomAt = (factor: number, cx = size.w / 2, cy = size.h / 2) => setView((v) => {
    const s = Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, v.s * factor));
    const k = s / v.s;
    return { s, tx: cx - (cx - v.tx) * k, ty: cy - (cy - v.ty) * k };
  });
  const centreOn = (n: GNode) => setView((v) => {
    const s = Math.max(v.s, 1);
    return { s, tx: size.w / 2 - n.x * s, ty: size.h * 0.4 - n.y * s };
  });

  /* Drag to pan, pinch to zoom. A drag that moved is not a tap. */
  const pointers = useRef(new Map<number, { x: number; y: number }>());
  const moved = useRef(false);
  const onPointerDown = (e: React.PointerEvent) => {
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
    pointers.current.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (pointers.current.size === 1) moved.current = false;
  };
  const onPointerMove = (e: React.PointerEvent) => {
    const p = pointers.current;
    const prev = p.get(e.pointerId);
    if (!prev) return;
    const rect = box.current!.getBoundingClientRect();
    if (p.size === 1) {
      const dx = e.clientX - prev.x, dy = e.clientY - prev.y;
      if (Math.abs(dx) + Math.abs(dy) > 2) moved.current = true;
      setView((v) => ({ ...v, tx: v.tx + dx, ty: v.ty + dy }));
    } else if (p.size === 2) {
      const [other] = [...p.entries()].filter(([id]) => id !== e.pointerId).map(([, q]) => q);
      const before = Math.hypot(prev.x - other.x, prev.y - other.y);
      const after = Math.hypot(e.clientX - other.x, e.clientY - other.y);
      moved.current = true;
      if (before > 0) zoomAt(after / before, (e.clientX + other.x) / 2 - rect.left, (e.clientY + other.y) / 2 - rect.top);
    }
    p.set(e.pointerId, { x: e.clientX, y: e.clientY });
  };
  const onPointerUp = (e: React.PointerEvent) => { pointers.current.delete(e.pointerId); };
  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const wheel = (e: WheelEvent) => {
      e.preventDefault();
      const r = el.getBoundingClientRect();
      zoomAt(Math.exp(-e.deltaY * 0.0015), e.clientX - r.left, e.clientY - r.top);
    };
    el.addEventListener('wheel', wheel, { passive: false });
    return () => el.removeEventListener('wheel', wheel);
  });

  const selected = sel ? byKey.get(sel) : undefined;
  const rel: GEdge[] = selected ? focusEdges(selected, g.nodes, g.vectors) : g.overview;
  const lit = useMemo(() => {
    if (!sel) return null;
    const s = new Set([sel]);
    for (const e of [...g.edges, ...rel]) { if (e.a === sel) s.add(e.b); if (e.b === sel) s.add(e.a); }
    return s;
  }, [sel, g.edges, rel]);
  const nearAll = selected ? closest(everything.nodes.find((n) => n.key === selected.key) ?? selected, everything.nodes, everything.vectors, 4) : [];

  // A category's colour runs down its whole branch.
  const hue = (n: GNode) => (n.kind === 'own' ? hueOf(n.topicId!) : hueOf(n.top || n.key));
  const P = (n: GNode): [number, number] => [n.x * view.s + view.tx, n.y * view.s + view.ty];
  const pick = (key: string) => {
    if (!byKey.has(key)) setOpts((o) => ({ ...o, scope: 'all' })); // it lives outside your topics
    setSel(key);
  };
  // Centre a node once it is picked -- also after the scope changed under it.
  useEffect(() => { const n = sel ? byKey.get(sel) : undefined; if (n) centreOn(n); // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sel, byKey]);

  const edgePath = (a: GNode, b: GNode, bend: number) => {
    const [ax, ay] = P(a), [bx, by] = P(b);
    const mx = (ax + bx) / 2, my = (ay + by) / 2;
    const dx = by - ay, dy = ax - bx;
    const k = bend / (Math.hypot(dx, dy) || 1);
    return `M${ax.toFixed(1)},${ay.toFixed(1)} Q${(mx + dx * k).toFixed(1)},${(my + dy * k).toFixed(1)} ${bx.toFixed(1)},${by.toFixed(1)}`;
  };

  const named = useMemo(() => {
    const out = new Set<string>();
    const k = labelScale(view.s);
    const boxes: [number, number, number, number][] = [];
    // Focused first, then what it lights, then topics (yours first), then
    // subtopics (yours first), then sources. The hub is small and always drawn.
    const first = (n: GNode) => (n.key === sel ? -20 : lit?.has(n.key) ? -10 : 0) + rank(n) * 2 + (n.followed ? 0 : 1);
    const ranked = g.nodes.filter((n) => n.kind !== 'area').sort((a, b) => first(a) - first(b));
    for (const n of ranked) {
      const x = n.x * view.s + view.tx, y = n.y * view.s + view.ty;
      const hw = (n.w * k) / 2, hh = (n.h * k) / 2;
      const b: [number, number, number, number] = [x - hw - 3, y - hh - 2, x + hw + 3, y + hh + 2];
      if (!alwaysNamed(n) && boxes.some((o) => b[0] < o[2] && o[0] < b[2] && b[1] < o[3] && o[1] < b[3])) continue;
      boxes.push(b);
      out.add(n.key);
    }
    return out;
  }, [g.nodes, view, sel, lit]);

  const draw = (n: GNode) => {
    const dim = lit && !lit.has(n.key);
    const focus = n.key === sel;
    const tap = () => { if (moved.current) return; setSel(focus ? null : n.key); };
    const props = {
      key: n.key, className: `node tappable${dim ? ' dim' : ''}${focus ? ' focus' : ''}`,
      onClick: tap, tabIndex: 0, role: 'button', 'aria-label': `${kindName(n)}: ${n.label}`,
      onKeyDown: (e: React.KeyboardEvent) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setSel(focus ? null : n.key); } },
    };
    const [x, y] = P(n);
    const c = hue(n);
    if (n.kind === 'area') {
      return <g {...props}><rect x={x - n.w / 2} y={y - n.h / 2} width={n.w} height={n.h} rx={n.h / 2} fill="var(--fg)" />
        <text x={x} y={y + 5} textAnchor="middle" fontSize={14} fontWeight={800} fill="var(--bg)">{n.label}</text></g>;
    }
    if (!named.has(n.key)) {
      const r = n.kind === 'src' ? 3.5 : n.kind === 'leaf' ? 4.5 : 7;
      const fill = n.kind === 'src' ? 'var(--muted)' : c;
      return <g {...props}><circle cx={x} cy={y} r={14} fill="transparent" />
        <circle cx={x} cy={y} r={r} fill={n.followed ? fill : 'var(--surface)'} stroke={fill} strokeWidth={1.8} opacity={0.85} /></g>;
    }
    const text = n.label.length > 26 ? n.label.slice(0, 25) + '…' : n.label;
    const k = labelScale(view.s);
    const left = -n.w / 2, top = -n.h / 2;
    const at = `translate(${x.toFixed(1)},${y.toFixed(1)}) scale(${k.toFixed(3)})`;
    if (n.kind === 'branch' || n.kind === 'own') {
      // A category or one of yours is a pill in its colour: solid when you
      // follow it, a tint when you do not. Deeper topics are smaller outlines.
      const big = n.depth === 1 || n.kind === 'own';
      const fill = n.followed ? c : big ? `color-mix(in srgb, ${c} 12%, var(--surface))` : 'var(--surface)';
      return <g {...props}><g transform={at}>
        <rect x={left} y={top} width={n.w} height={n.h} rx={n.h / 2} fill={fill} stroke={c} strokeWidth={n.followed ? 0 : 1.6} strokeOpacity={big ? 0.7 : 0.5} />
        <text x={0} y={big ? 4.6 : 4.2} textAnchor="middle" fontSize={big ? 13 : 12} fontWeight={big ? 700 : 650} fill={n.followed ? '#fff' : c}>{text}</text>
      </g></g>;
    }
    if (n.kind === 'leaf') {
      // The smallest topics: a dot and a name, nothing around them.
      return <g {...props}><g transform={at}>
        <rect x={left} y={top} width={n.w} height={n.h} fill="transparent" />
        <circle cx={left + 5} cy={0} r={4} fill={n.followed ? c : 'var(--surface)'} stroke={c} strokeWidth={1.6} />
        <text x={left + 14} y={4} fontSize={11.5} fontWeight={n.followed ? 650 : 500} fill={n.followed ? 'var(--fg)' : 'var(--muted)'}>{text}</text>
      </g></g>;
    }
    return <g {...props}><g transform={at}>
      <rect x={left} y={top} width={n.w} height={n.h} rx={6} fill="var(--surface-2)" stroke="var(--line)" />
      <text x={0} y={4} textAnchor="middle" fontSize={11} fill="var(--muted)">{text}</text>
    </g></g>;
  };

  const order: Record<GNode['kind'], number> = { src: 0, leaf: 1, branch: 2, own: 3, area: 4 };
  const drawn = [...g.nodes].sort((a, b) => order[a.kind] - order[b.kind] || (a.key === sel ? 1 : 0) - (b.key === sel ? 1 : 0));
  const parentOfSel = selected?.parent ? byKey.get(`n:${selected.parent}`) : undefined;
  const topicOfSel = selected?.topicId ? profile.topics.find((t) => t.id === selected.topicId) : undefined;

  return (
    <>
      <div className="bar">
        <button className="icon-btn" onClick={onBack} aria-label="Back">{ICON.back}</button>
        <div className="grow"><div className="crumbs">{profile.name}</div><div className="title-sm">Your tree</div></div>
      </div>
      <div className="tree-filters">
        <div className="switch" role="group" aria-label="Show">
          <button aria-pressed={opts.scope === 'mine'} onClick={() => setOpts((o) => ({ ...o, scope: 'mine' }))}>Yours</button>
          <button aria-pressed={opts.scope === 'all'} onClick={() => setOpts((o) => ({ ...o, scope: 'all' }))}>All</button>
        </div>
        <button className="chip" aria-pressed={opts.related} onClick={() => setOpts((o) => ({ ...o, related: !o.related }))}>Related</button>
        <button className="chip" aria-pressed={opts.sources} onClick={() => setOpts((o) => ({ ...o, sources: !o.sources }))}>Sources</button>
      </div>
      <div className="graph" ref={box} onPointerDown={onPointerDown} onPointerMove={onPointerMove}
        onPointerUp={onPointerUp} onPointerCancel={onPointerUp}
        onClick={(e) => { if (!moved.current && (e.target as Element).tagName === 'svg') setSel(null); }}>
        {g.nodes.length === 0
          ? <p className="hint" style={{ padding: 16 }}>You have no topics yet. Show all of AI to look around.</p>
          : (
            <svg width={size.w} height={size.h} role="img" aria-label="Your topics and how they relate">
              {g.edges.map((e) => {
                const a = byKey.get(e.a), b = byKey.get(e.b);
                if (!a || !b) return null;
                const on = !!sel && (e.a === sel || e.b === sel);
                return <path key={`${e.a}>${e.b}`} className={`edge ${e.kind}${lit && !on ? ' dim' : ''}${on ? ' on' : ''}`} d={edgePath(a, b, 10)} />;
              })}
              {rel.map((e) => {
                const a = byKey.get(e.a), b = byKey.get(e.b);
                if (!a || !b) return null;
                return <path key={`rel:${e.a}|${e.b}`} className={`edge rel${sel ? ' on' : ''}`} d={edgePath(a, b, 36)} />;
              })}
              {drawn.map(draw)}
            </svg>
          )}
        <div className="graph-tools" onPointerDown={(e) => e.stopPropagation()}>
          <button onClick={() => zoomAt(1.35)} aria-label="Zoom in">+</button>
          <button onClick={() => zoomAt(1 / 1.35)} aria-label="Zoom out">−</button>
          <button onClick={() => fit(true)} aria-label="Show everything">⤢</button>
        </div>
      </div>
      <div className="tree-panel">
        {selected ? (
          <>
            <button className="x panel-x" onClick={() => setSel(null)} aria-label="Clear">✕</button>
            <div>
              <div className="eyebrow">{kindName(selected)}{parentOfSel ? ` in ${parentOfSel.label}` : ''}</div>
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
            {selected.kind !== 'src' && (selected.topicId || selected.slug) && (
              <div className="row">
                <button className="btn primary" onClick={() => (selected.topicId
                  ? onOpen(selected.topicId, selected.slug && selected.slug !== topicOfSel?.spine ? selected.slug : undefined)
                  : onOpen(selected.slug!))}>Open</button>
                {selected.mine || selected.kind === 'own'
                  ? <span className="following-tag">✓ Following</span>
                  : selected.slug && <button className="btn" onClick={() => onAdd(selected.slug!)}>Follow</button>}
              </div>
            )}
          </>
        ) : (
          <p className="hint">Drag and pinch to explore. Tap a topic to see what it is closest to; dashed lines join topics whose stories are alike.</p>
        )}
      </div>
    </>
  );
}
