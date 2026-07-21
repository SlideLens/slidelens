import type { SlideTimingIn } from "@/api/schemas";

/**
 * Tracks (slide_num, start, end) in seconds as the user pages through slides
 * during a rehearsal recording. Pure — takes an injectable clock so it's
 * testable without a real timer or MediaRecorder.
 */
export class SlideTimingTracker {
  private readonly now: () => number;
  private startedAtMs = 0;
  private timings: { slide_num: number; start: number; end: number | null }[] = [];

  constructor(now: () => number = () => performance.now()) {
    this.now = now;
  }

  start(initialSlideNum: number): void {
    this.startedAtMs = this.now();
    this.timings = [{ slide_num: initialSlideNum, start: 0, end: null }];
  }

  private elapsedSeconds(): number {
    return (this.now() - this.startedAtMs) / 1000;
  }

  switchTo(slideNum: number): void {
    const elapsed = this.elapsedSeconds();
    const last = this.timings[this.timings.length - 1];
    if (last) last.end = elapsed;
    this.timings.push({ slide_num: slideNum, start: elapsed, end: null });
  }

  /** Finalizes the open entry and returns the full timing list. Safe to call once, at stop. */
  stop(): SlideTimingIn[] {
    const elapsed = this.elapsedSeconds();
    const last = this.timings[this.timings.length - 1];
    if (last && last.end === null) last.end = elapsed;
    return this.timings
      .filter((t) => t.end !== null)
      .map((t) => ({ slide_num: t.slide_num, start: t.start, end: t.end as number }));
  }
}
