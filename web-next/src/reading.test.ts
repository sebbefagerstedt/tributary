import { describe, expect, it } from 'vitest';
import { ReadingTracker } from './reading';

describe('reading the feed', () => {
  it('marks a card read once it has been on screen and scrolled away over the top', () => {
    const t = new ReadingTracker();
    t.show(1);
    expect(t.passed(1)).toEqual([1]);
    expect(t.passed(1)).toEqual([]);           // once
  });
  it('never marks a card that was never on screen, wherever the page opened', () => {
    const t = new ReadingTracker();
    expect(t.passed(2)).toEqual([]);
  });
  it('marks every card shown above "You\'re all caught up" when you reach it', () => {
    const t = new ReadingTracker();
    t.show(1); t.show(2); t.show(3);
    expect(t.passed(1)).toEqual([1]);
    expect(t.reachedEnd().sort()).toEqual([2, 3]);
    expect(t.reachedEnd()).toEqual([]);
  });
});
