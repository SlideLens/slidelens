import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import { apiClient } from "@/api/client";
import type { ReportOut } from "@/api/schemas";

/** GET /reviews/{id}/report — only meaningful once the Review is done (409 otherwise). */
export function useReport(reviewId: string | undefined, enabled: boolean): UseQueryResult<ReportOut> {
  return useQuery({
    queryKey: ["report", reviewId],
    queryFn: () => apiClient.request<ReportOut>(`/reviews/${reviewId}/report`),
    enabled: Boolean(reviewId) && enabled,
  });
}
