import { Fragment, useMemo } from "react";
import type { Finding } from "@/api/schemas";
import { cn } from "@/lib/utils";

export interface SlideViewerProps {
  slideNum: number;
  findings: Finding[];
  activeFindingId?: string | null;
  onFrameClick: (findingId: string) => void;
  /** Находка → её порядковый номер (для связки пина на слайде с карточкой в полях). */
  numberOf?: (findingId: string) => number | undefined;
  /**
   * Сырой рендер слайда (``GET /reviews/{id}/slides``). Если он есть — рамки Находок
   * рисует этот компонент, и они слушаются фильтров. Если нет, откатываемся на
   * ``screenshot_url``: в него рамки уже впечатаны сервером, и свои поверх них не
   * рисуем, иначе получается двойной контур.
   */
  slideUrl?: string | null;
}

const SEVERITY_TEXT: Record<Finding["severity"], string> = {
  CRITICAL: "text-severity-critical",
  MAJOR: "text-severity-major",
  MINOR: "text-severity-minor",
};

const SEVERITY_BG: Record<Finding["severity"], string> = {
  CRITICAL: "bg-severity-critical",
  MAJOR: "bg-severity-major",
  MINOR: "bg-severity-minor",
};

/**
 * Доля площади слайда, начиная с которой bbox перестаёт на что-либо указывать:
 * модель не нашла конкретную область и вернула рамку «во весь слайд». Рисовать
 * такую рамку нельзя — она накрывает собой все настоящие области под ней.
 * Дублирует ``SLIDE_WIDE_BBOX_AREA`` из ``core/constants.py``.
 */
const SLIDE_WIDE_AREA = 0.8;

const PIN_PX = 24;
const PIN_INSET_PX = 3;
/** Шаг расталкивания пинов, попавших в одну точку (bbox'ы часто делят угол). */
const PIN_STACK_PX = PIN_PX + 2;

interface PlacedFinding {
  finding: Finding;
  number: number;
  /** Левый/верхний край bbox в процентах — якорь и рамки, и пина. */
  leftPct: number;
  topPct: number;
  widthPct: number;
  heightPct: number;
  /** Смещение пина по вертикали, если в этой точке он не первый. */
  stackOffsetPx: number;
}

/** Пин ставится ВНУТРЬ угла bbox и прижимается к краю картинки — иначе bbox
 * вида `x=0,y=0` уводит половину пина за `overflow-hidden` и по нему не попасть. */
function pinInset(pct: number) {
  return `min(${pct}%, calc(100% - ${PIN_PX + PIN_INSET_PX}px))`;
}

export function SlideViewer({
  slideNum,
  findings,
  activeFindingId,
  onFrameClick,
  numberOf,
  slideUrl,
}: SlideViewerProps) {
  const annotatedUrl = findings.find((f) => f.screenshot_url)?.screenshot_url;
  const imageUrl = slideUrl ?? annotatedUrl;
  /** Рамки уже впечатаны в картинку — свои не рисуем. */
  const framesBakedIn = !slideUrl && Boolean(annotatedUrl);

  const { regions, slideWide } = useMemo(() => {
    const framed = findings.filter((f) => f.bbox != null);

    const placed: PlacedFinding[] = [];
    const wide: PlacedFinding[] = [];
    // Пины, попавшие в одну и ту же точку (сетка 5%), расталкиваем по вертикали.
    const occupied = new Map<string, number>();

    framed.forEach((finding, index) => {
      const bbox = finding.bbox!;
      const leftPct = bbox.x * 100;
      const topPct = bbox.y * 100;
      const key = `${Math.round(leftPct / 5)}:${Math.round(topPct / 5)}`;
      const stack = occupied.get(key) ?? 0;
      occupied.set(key, stack + 1);

      const entry: PlacedFinding = {
        finding,
        number: numberOf?.(finding.id) ?? index + 1,
        leftPct,
        topPct,
        widthPct: bbox.w * 100,
        heightPct: bbox.h * 100,
        // Ниже середины слайда расталкиваем вверх, чтобы не уехать за нижний край.
        stackOffsetPx: stack * PIN_STACK_PX * (topPct > 60 ? -1 : 1),
      };
      if (bbox.w * bbox.h >= SLIDE_WIDE_AREA) wide.push(entry);
      else placed.push(entry);
    });

    // Мелкие области рисуем и кликаем поверх крупных, иначе большой bbox
    // перехватывает клики по вложенному в него маленькому.
    placed.sort((a, b) => b.widthPct * b.heightPct - a.widthPct * a.heightPct);
    return { regions: placed, slideWide: wide };
  }, [findings, numberOf]);

  return (
    <div
      className={cn(
        // self-start: without it, the parent grid row (slide | finding cards)
        // stretches this box to match the taller sibling column, and the
        // pin/frame % math ends up resolving against that stretched height
        // instead of the image's actual rendered height.
        "relative w-full self-start overflow-hidden rounded-lg border border-border bg-white",
        !imageUrl && "aspect-video",
      )}
    >
      {imageUrl && <img src={imageUrl} alt={`Слайд ${slideNum}`} className="block h-auto w-full" />}
      <div className="absolute left-3 top-3 z-30 rounded bg-foreground/80 px-2 py-0.5 font-mono text-[10.5px] uppercase tracking-wide text-white">
        Слайд {slideNum}
      </div>

      {regions.map(({ finding, number, leftPct, topPct, widthPct, heightPct, stackOffsetPx }, rank) => {
        const isActive = finding.id === activeFindingId;
        return (
          <Fragment key={finding.id}>
            {/* Вся область bbox — одна кликабельная мишень. В покое это уголки,
                а не сплошная рамка: на слайде их бывает до семи, и сплошные
                прямоугольники превращают слайд в кашу. */}
            <button
              type="button"
              title={finding.title}
              aria-current={isActive}
              onClick={() => onFrameClick(finding.id)}
              className={cn(
                "group absolute cursor-pointer rounded-sm bg-transparent transition-colors",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent",
                SEVERITY_TEXT[finding.severity],
                isActive && "bg-current/10 ring-2 ring-current",
                !isActive && "hover:bg-current/5 hover:ring-2 hover:ring-current/60",
              )}
              style={{
                left: `${leftPct}%`,
                top: `${topPct}%`,
                width: `${widthPct}%`,
                height: `${heightPct}%`,
                zIndex: 10 + rank,
              }}
            >
              <span className="sr-only">{finding.title}</span>
              {!framesBakedIn && (
                <span
                  aria-hidden
                  className={cn(
                    "absolute inset-0 transition-opacity",
                    isActive ? "opacity-0" : "opacity-100 group-hover:opacity-0",
                  )}
                >
                  <i className="absolute -left-px -top-px h-3.5 w-3.5 border-l-2 border-t-2 border-current" />
                  <i className="absolute -right-px -top-px h-3.5 w-3.5 border-r-2 border-t-2 border-current" />
                  <i className="absolute -bottom-px -left-px h-3.5 w-3.5 border-b-2 border-l-2 border-current" />
                  <i className="absolute -bottom-px -right-px h-3.5 w-3.5 border-b-2 border-r-2 border-current" />
                </span>
              )}
            </button>
            <span
              aria-hidden
              className={cn(
                "pointer-events-none absolute flex h-6 w-6 items-center justify-center rounded-full",
                "font-mono text-xs font-bold text-white shadow ring-2 ring-white transition-transform",
                SEVERITY_BG[finding.severity],
                isActive && "scale-110 ring-accent",
              )}
              style={{
                left: pinInset(leftPct),
                top: pinInset(topPct),
                transform: `translate(${PIN_INSET_PX}px, ${PIN_INSET_PX + stackOffsetPx}px)`,
                zIndex: 20 + rank,
              }}
            >
              {number}
            </span>
          </Fragment>
        );
      })}

      {slideWide.length > 0 && (
        <div className="absolute bottom-2 left-2 z-30 flex items-center gap-1.5 rounded-full bg-foreground/80 py-1 pl-1 pr-2.5">
          {slideWide.map(({ finding, number }) => (
            <button
              key={finding.id}
              type="button"
              title={finding.title}
              aria-current={finding.id === activeFindingId}
              onClick={() => onFrameClick(finding.id)}
              className={cn(
                "flex h-5 w-5 items-center justify-center rounded-full font-mono text-[10px] font-bold",
                "text-white ring-1 ring-white/70 transition-transform hover:scale-110",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent",
                SEVERITY_BG[finding.severity],
                finding.id === activeFindingId && "scale-110 ring-2 ring-accent",
              )}
            >
              {number}
            </button>
          ))}
          <span className="font-mono text-[10px] uppercase tracking-wide text-white">весь слайд</span>
        </div>
      )}
    </div>
  );
}
