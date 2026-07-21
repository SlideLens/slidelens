import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import { apiClient } from "@/api/client";
import type { RehearsalReportOut } from "@/api/schemas";

/** GET /rehearsals/{id}/report — only meaningful once the attempt is done (409 otherwise). */
export function useRehearsalReport(
  rehearsalId: string | undefined,
  enabled: boolean,
): UseQueryResult<RehearsalReportOut> {
  return useQuery({
    queryKey: ["rehearsal-report", rehearsalId],
    queryFn: () => apiClient.request<RehearsalReportOut>(`/rehearsals/${rehearsalId}/report`),
    enabled: Boolean(rehearsalId) && enabled,
  });
}
