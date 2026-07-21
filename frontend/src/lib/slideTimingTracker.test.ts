import { describe, expect, it } from "vitest";
import { SlideTimingTracker } from "./slideTimingTracker";

function fakeClock(startMs = 0) {
  let now = startMs;
  return { now: () => now, advance: (ms: number) => (now += ms) };
}

describe("SlideTimingTracker", () => {
  it("tracks a single slide from start to stop", () => {
    const clock = fakeClock();
    const tracker = new SlideTimingTracker(clock.now);
    tracker.start(1);
    clock.advance(5000);
    expect(tracker.stop()).toEqual([{ slide_num: 1, start: 0, end: 5 }]);
  });

  it("closes the previous slide and opens the next on switchTo", () => {
    const clock = fakeClock();
    const tracker = new SlideTimingTracker(clock.now);
    tracker.start(1);
    clock.advance(3000);
    tracker.switchTo(2);
    clock.advance(7000);
    tracker.switchTo(3);
    clock.advance(2000);

    expect(tracker.stop()).toEqual([
      { slide_num: 1, start: 0, end: 3 },
      { slide_num: 2, start: 3, end: 10 },
      { slide_num: 3, start: 10, end: 12 },
    ]);
  });

  it("supports revisiting an earlier slide (duplicate slide_num entries)", () => {
    const clock = fakeClock();
    const tracker = new SlideTimingTracker(clock.now);
    tracker.start(1);
    clock.advance(2000);
    tracker.switchTo(2);
    clock.advance(2000);
    tracker.switchTo(1);
    clock.advance(1000);

    expect(tracker.stop()).toEqual([
      { slide_num: 1, start: 0, end: 2 },
      { slide_num: 2, start: 2, end: 4 },
      { slide_num: 1, start: 4, end: 5 },
    ]);
  });

  it("starting a new recording resets prior timings", () => {
    const clock = fakeClock();
    const tracker = new SlideTimingTracker(clock.now);
    tracker.start(1);
    clock.advance(5000);
    tracker.switchTo(2);
    clock.advance(1000);

    tracker.start(1);
    clock.advance(4000);
    expect(tracker.stop()).toEqual([{ slide_num: 1, start: 0, end: 4 }]);
  });
});
