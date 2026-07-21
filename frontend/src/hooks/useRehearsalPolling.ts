import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import { apiClient } from "@/api/client";
import type { RehearsalOut } from "@/api/schemas";

export const REHEARSAL_POLL_INTERVAL_MS = 5000;
const ACTIVE_STATUSES = new Set<RehearsalOut["status"]>(["queued", "processing"]);

export function rehearsalsQueryKey(reviewId: string | undefined) {
  return ["rehearsals", reviewId] as const;
}

export function rehearsalQueryKey(rehearsalId: string | undefined) {
  return ["rehearsal", rehearsalId] as const;
}

export function rehearsalPollInterval(status: RehearsalOut["status"] | undefined): number | false {
  return status && ACTIVE_STATUSES.has(status) ? REHEARSAL_POLL_INTERVAL_MS : false;
}

/** Past attempts for a Review, oldest first — feeds the progress-over-attempts view (П4). */
export function useRehearsals(reviewId: string | undefined): UseQueryResult<RehearsalOut[]> {
  return useQuery({
    queryKey: rehearsalsQueryKey(reviewId),
    queryFn: () => apiClient.request<RehearsalOut[]>(`/reviews/${reviewId}/rehearsals`),
    enabled: Boolean(reviewId),
  });
}

/** Single-rehearsal polling — stops once that attempt reaches done/failed. */
export function useRehearsalStatus(rehearsalId: string | undefined): UseQueryResult<RehearsalOut> {
  return useQuery({
    queryKey: rehearsalQueryKey(rehearsalId),
    queryFn: () => apiClient.request<RehearsalOut>(`/rehearsals/${rehearsalId}`),
    enabled: Boolean(rehearsalId),
    refetchInterval: (query) => rehearsalPollInterval(query.state.data?.status),
  });
}
