/* Touch, the way the apps this borrows from behave: a sheet follows your
   finger down and closes past a point, and the player reads a tap by which
   side it landed on and a swipe by its direction. */

import { PointerEvent as ReactPointerEvent, RefObject, useEffect, useRef } from 'react';

const CLOSE_AT = 90;      // px dragged down that closes a sheet
const FLICK = 0.5;        // px per ms: a quick flick closes it sooner
const SWIPE = 50;         // px sideways that counts as a swipe in the player
const TAP = 10;           // px of movement still read as a tap

const onControl = (target: EventTarget | null) =>
  target instanceof Element && !!target.closest('button, a, input, summary, label');

/* Drag a sheet down to close it. Only from its top: while its content is
   scrolled, a downward drag scrolls it back first, as on iOS — unless it
   starts on the grab handle. Listeners are native and not passive, so the
   page under the sheet does not scroll along. */
export function useDragToClose(ref: RefObject<HTMLElement>, onClose: () => void) {
  // The latest callback, so a re-render mid-drag does not rebind and drop it.
  const close = useRef(onClose);
  close.current = onClose;
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    let y0 = 0, t0 = 0, dy = 0, active = false;
    const start = (e: TouchEvent) => {
      const fromGrab = e.target instanceof Element && !!e.target.closest('.grab');
      active = fromGrab || el.scrollTop <= 0;
      y0 = e.touches[0].clientY; t0 = Date.now(); dy = 0;
      el.style.transition = 'none';
    };
    const move = (e: TouchEvent) => {
      if (!active) return;
      dy = e.touches[0].clientY - y0;
      if (dy <= 0) { el.style.transform = ''; if (dy < -TAP) active = false; return; }
      e.preventDefault();
      el.style.transform = `translateY(${dy}px)`;
    };
    const end = () => {
      if (!active) return;
      active = false;
      const fast = dy / Math.max(1, Date.now() - t0) > FLICK && dy > 30;
      el.style.transition = 'transform .18s ease-out';
      if (dy > CLOSE_AT || fast) {
        el.style.transform = 'translateY(100%)';
        window.setTimeout(() => close.current(), 160);
      } else {
        el.style.transform = '';
      }
    };
    el.addEventListener('touchstart', start, { passive: true });
    el.addEventListener('touchmove', move, { passive: false });
    el.addEventListener('touchend', end);
    el.addEventListener('touchcancel', end);
    return () => {
      el.removeEventListener('touchstart', start);
      el.removeEventListener('touchmove', move);
      el.removeEventListener('touchend', end);
      el.removeEventListener('touchcancel', end);
    };
  }, [ref]);
}

/* The player's whole screen is the control: a tap on the left third goes
   back, anywhere else forward; a sideways swipe steps, a swipe down closes.
   Buttons and links on it keep their own taps. */
export function usePlayerGestures(step: (d: number) => void, close: () => void) {
  const at = useRef<{ x: number; y: number } | null>(null);
  return {
    onPointerDown: (e: ReactPointerEvent) => {
      at.current = onControl(e.target) ? null : { x: e.clientX, y: e.clientY };
    },
    onPointerUp: (e: ReactPointerEvent) => {
      const start = at.current;
      at.current = null;
      if (!start) return;
      const dx = e.clientX - start.x, dy = e.clientY - start.y;
      if (dy > CLOSE_AT && dy > Math.abs(dx)) close();
      else if (Math.abs(dx) > SWIPE && Math.abs(dx) > Math.abs(dy)) step(dx < 0 ? 1 : -1);
      else if (Math.abs(dx) < TAP && Math.abs(dy) < TAP) {
        const box = (e.currentTarget as HTMLElement).getBoundingClientRect();
        step(e.clientX - box.left < box.width / 3 ? -1 : 1);
      }
    },
    onPointerCancel: () => { at.current = null; },
  };
}
