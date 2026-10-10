/* Reading the feed marks what you read (2026-10-10: "News are not removed from
   new if I use the feed"). A card counts as read once it has been on screen
   and then scrolled away over the top -- or, for the last few, once you have
   scrolled down to "You're all caught up" below them. A card never shown is
   never marked, whatever the scroll position a page opens at. This is read
   state only; nothing here reaches the ranking (CLAUDE.md, ground rules). */

import { useCallback, useEffect, useRef } from 'react';

/* The rule, kept apart from the DOM so it can be tested. */
export class ReadingTracker {
  private shown = new Set<number>();
  private done = new Set<number>();

  /** A card came on screen. */
  show(id: number) { if (!this.done.has(id)) this.shown.add(id); }

  /** A card left the screen over the top edge: read, if it was ever shown. */
  passed(id: number): number[] {
    if (!this.shown.has(id) || this.done.has(id)) return [];
    this.done.add(id);
    return [id];
  }

  /** "You're all caught up" came into view after scrolling: every card shown
      above it is read. */
  reachedEnd(): number[] {
    const out = [...this.shown].filter((id) => !this.done.has(id));
    for (const id of out) this.done.add(id);
    return out;
  }
}

const ON_SCREEN = 0.5;  // half a card visible is a card shown
const SCROLLED = 40;    // px moved since the page opened before the end counts
const FLUSH_MS = 500;   // marks are saved together, not one request per card

export function useReadOnScroll(onRead: (ids: number[]) => void) {
  const tracker = useRef(new ReadingTracker());
  const pending = useRef(new Set<number>());
  const timer = useRef<number | undefined>(undefined);
  const save = useRef(onRead);
  save.current = onRead;
  const els = useRef(new Map<Element, number>());
  const refs = useRef(new Map<number, (el: Element | null) => void>());
  const observer = useRef<IntersectionObserver | null>(null);
  const end = useRef<IntersectionObserver | null>(null);
  const endEl = useRef<Element | null>(null);
  const endVisible = useRef(false);
  const startY = useRef(typeof window === 'undefined' ? 0 : window.scrollY);

  const flush = useCallback(() => {
    window.clearTimeout(timer.current);
    timer.current = undefined;
    if (!pending.current.size) return;
    const ids = [...pending.current];
    pending.current.clear();
    save.current(ids);
  }, []);
  const queue = useCallback((ids: number[]) => {
    if (!ids.length) return;
    for (const id of ids) pending.current.add(id);
    if (timer.current === undefined) timer.current = window.setTimeout(flush, FLUSH_MS);
  }, [flush]);

  useEffect(() => {
    if (typeof IntersectionObserver === 'undefined') return undefined;
    observer.current = new IntersectionObserver((entries) => {
      for (const e of entries) {
        const id = els.current.get(e.target);
        if (id === undefined) continue;
        if (e.isIntersecting && e.intersectionRatio >= ON_SCREEN) tracker.current.show(id);
        else if (!e.isIntersecting && e.boundingClientRect.bottom <= (e.rootBounds?.top ?? 0)) {
          queue(tracker.current.passed(id));
        }
      }
    }, { threshold: [0, ON_SCREEN] });
    const atEnd = () => {
      const scrolled = Math.abs(window.scrollY - startY.current) > SCROLLED;
      if (scrolled && endVisible.current) queue(tracker.current.reachedEnd());
    };
    end.current = new IntersectionObserver((entries) => {
      endVisible.current = entries[entries.length - 1].isIntersecting;
      atEnd();
    });
    for (const el of els.current.keys()) observer.current.observe(el);
    if (endEl.current) end.current.observe(endEl.current);
    // A short page can show the marker the whole time; scrolling still counts.
    window.addEventListener('scroll', atEnd, { passive: true });
    return () => {
      window.removeEventListener('scroll', atEnd);
      observer.current?.disconnect();
      end.current?.disconnect();
      flush();
    };
  }, [queue, flush]);

  /* A ref for each card that should count: `cardRef(id)`, the same function
     every render, so React does not detach and re-attach it each time. */
  const cardRef = useCallback((id: number) => {
    let ref = refs.current.get(id);
    if (!ref) {
      ref = (el: Element | null) => {
        if (el) {
          els.current.set(el, id);
          observer.current?.observe(el);
          return;
        }
        for (const [k, v] of els.current) {
          if (v === id) { observer.current?.unobserve(k); els.current.delete(k); }
        }
      };
      refs.current.set(id, ref);
    }
    return ref;
  }, []);
  /* A ref for the "You're all caught up" marker. */
  const endRef = useCallback((el: Element | null) => {
    if (endEl.current && end.current) end.current.unobserve(endEl.current);
    endEl.current = el;
    if (el) end.current?.observe(el);
  }, []);
  return { cardRef, endRef };
}
