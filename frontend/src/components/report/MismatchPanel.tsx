import type { Finding } from "@/api/schemas";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export interface MismatchPanelProps {
  findings: Finding[];
}

/** Only rendered by ReviewReport when a Запись питча was attached. */
export function MismatchPanel({ findings }: MismatchPanelProps) {
  const mismatches = findings.filter((f) => f.category === "SPEECH_MISMATCH");

  return (
    <Card>
      <CardHeader>
        <CardTitle>Речь ↔ слайды</CardTitle>
      </CardHeader>
      <CardContent>
        {mismatches.length === 0 ? (
          <p className="text-sm text-muted-foreground">Противоречий между речью и слайдами не найдено.</p>
        ) : (
          <ul className="flex flex-col gap-3">
            {mismatches.map((finding) => (
              <li key={finding.id} className="text-sm">
                <span className="font-medium">
                  {finding.slide_num != null ? `Слайд ${finding.slide_num}: ` : ""}
                </span>
                {finding.description}
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
