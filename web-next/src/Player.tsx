/* A topic's new stories, full screen, one at a time. No timer: it waits for the
   reader (VISION.md, principle 6). Each story is marked read as it is shown. */

import { useEffect } from 'react';
import { Story, agoLabel } from './data';
import { Topic } from './state';
import { KIND_WORD, hueOf, kindColour } from './ui';

export function Player({ topic, queue, index, onStep, onClose, onRead, onSeen }: {
  topic: Topic; queue: Story[]; index: number;
  onStep: (d: number) => void; onClose: () => void; onRead: (s: Story) => void; onSeen: (s: Story) => void;
}) {
  const s = queue[index];
  useEffect(() => { if (s) onSeen(s); }, [s, onSeen]);
  if (!s) return null;
  return (
    <div className="player">
      <div className="stage" style={{ background: `linear-gradient(170deg, ${kindColour(s.kind)}, #0b1210 85%)` }}>
        {s.media_url && <img className="player-art" src={s.media_url} alt="" referrerPolicy="no-referrer" />}
        <div className="bars">{queue.map((q, j) => <i key={q.story_id} className={j <= index ? 'on' : ''} />)}</div>
        <div className="top">
          <span className="face" style={{ background: hueOf(topic.id) }}>{topic.name[0]}</span>
          <b>{topic.name}</b>
          <button className="close" onClick={onClose} aria-label="Close">✕</button>
        </div>
        <button className="tap l" onClick={() => onStep(-1)} aria-label="Previous story" />
        <button className="tap r" onClick={() => onStep(1)} aria-label="Next story" />
        <div className="body">
          <span className="eyebrow light">{KIND_WORD[s.kind] || s.kind} · {s.source} · {agoLabel(s.published_at)}</span>
          <h2>{s.title}</h2>
          {s.summary && <p>{s.summary}</p>}
          <button className="btn solid-light" onClick={() => onRead(s)}>Read the story</button>
          <span className="hint light">Tap the right side for the next story. No timer — it waits for you.</span>
        </div>
      </div>
    </div>
  );
}
