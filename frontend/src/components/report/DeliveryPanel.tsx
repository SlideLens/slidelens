import type { DeliveryMetrics } from "@/api/schemas";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { pluralizeRu } from "@/lib/pluralize";

export interface DeliveryPanelProps {
  delivery: DeliveryMetrics;
}

/** Only rendered by ReviewReport when a Запись питча was attached. */
export function DeliveryPanel({ delivery }: DeliveryPanelProps) {
  const fillerEntries = Object.entries(delivery.filler_words ?? {});
  const longPauses = delivery.long_pauses ?? [];

  return (
    <Card>
      <CardHeader>
        <CardTitle>Подача</CardTitle>
      </CardHeader>
      <CardContent className="grid gap-4 sm:grid-cols-3">
        <div>
          <div className="font-mono text-2xl font-semibold tabular-nums">
            {Math.round(delivery.words_per_minute ?? 0)}
          </div>
          <div className="text-sm text-muted-foreground">слов/мин</div>
        </div>
        <div>
          <div className="font-mono text-2xl font-semibold tabular-nums">
            {fillerEntries.reduce((sum, [, count]) => sum + count, 0)}
          </div>
          <div className="text-sm text-muted-foreground">
            {pluralizeRu(fillerEntries.reduce((sum, [, count]) => sum + count, 0), [
              "слово-паразит",
              "слова-паразита",
              "слов-паразитов",
            ])}
            {fillerEntries.length > 0 && (
              <>
                {": "}
                {fillerEntries.map(([word, count]) => `«${word}» (${count})`).join(", ")}
              </>
            )}
          </div>
        </div>
        <div>
          <div className="font-mono text-2xl font-semibold tabular-nums">{longPauses.length}</div>
          <div className="text-sm text-muted-foreground">
            {pluralizeRu(longPauses.length, ["длинная пауза", "длинные паузы", "длинных пауз"])} (&gt;
            3 с)
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
