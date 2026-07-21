import { cn } from "@/lib/utils";

export interface ScoreGaugeProps {
  score: number;
  className?: string;
}

/** Shared by the compact score badge (ReviewCard) so the colour bands stay in one place. */
export function bandColor(score: number): string {
  if (score >= 80) return "var(--color-status-done)";
  if (score >= 50) return "var(--color-severity-major)";
  return "var(--color-severity-critical)";
}

const TICK_RADIUS = 44;
const ARC_RADIUS = 35;
const ARC_CIRCUMFERENCE = 2 * Math.PI * ARC_RADIUS;

/** Скор 0–100 — измерительный циферблат: внешняя шкала делений + дуга прогресса. */
export function ScoreGauge({ score, className }: ScoreGaugeProps) {
  const clamped = Math.min(100, Math.max(0, score));
  const color = bandColor(clamped);
  const offset = ARC_CIRCUMFERENCE * (1 - clamped / 100);

  return (
    <svg
      width={84}
      height={84}
      viewBox="0 0 100 100"
      className={cn("shrink-0", className)}
      role="img"
      aria-label={`Скор ${clamped} из 100`}
    >
      <circle
        cx={50}
        cy={50}
        r={TICK_RADIUS}
        fill="none"
        stroke="var(--color-border)"
        strokeWidth={1}
        strokeDasharray="1 7.3"
      />
      <circle cx={50} cy={50} r={ARC_RADIUS} fill="none" stroke="var(--color-border)" strokeWidth={8} />
      <circle
        cx={50}
        cy={50}
        r={ARC_RADIUS}
        fill="none"
        stroke={color}
        strokeWidth={8}
        strokeLinecap="round"
        strokeDasharray={ARC_CIRCUMFERENCE}
        strokeDashoffset={offset}
        transform="rotate(-90 50 50)"
        style={{ transition: "stroke-dashoffset 0.4s ease" }}
      />
      <text
        x={50}
        y={48}
        textAnchor="middle"
        fontSize={24}
        fontWeight={800}
        fill="var(--color-foreground)"
        style={{ fontVariantNumeric: "tabular-nums" }}
      >
        {clamped}
      </text>
      <text
        x={50}
        y={63}
        textAnchor="middle"
        fontFamily="var(--font-mono)"
        fontSize={6.5}
        letterSpacing={1}
        fill="var(--color-muted-foreground)"
      >
        СКОР / 100
      </text>
    </svg>
  );
}
