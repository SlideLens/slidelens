import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import { apiClient } from "@/api/client";
import type { ReviewOut } from "@/api/schemas";

export const POLL_INTERVAL_MS = 5000;
const ACTIVE_STATUSES = new Set<ReviewOut["status"]>(["queued", "processing"]);

export function reviewsQueryKey() {
  return ["reviews"] as const;
}

export function reviewQueryKey(reviewId: string | undefined) {
  return ["review", reviewId] as const;
}

/** Pure decision logic, tested directly — avoids asserting on fake-timer flakiness. */
export function listPollInterval(reviews: ReviewOut[] | undefined): number | false {
  return reviews?.some((review) => ACTIVE_STATUSES.has(review.status)) ? POLL_INTERVAL_MS : false;
}

export function statusPollInterval(status: ReviewOut["status"] | undefined): number | false {
  return status && ACTIVE_STATUSES.has(status) ? POLL_INTERVAL_MS : false;
}

/** List polling for the cabinet — stops once nothing visible is queued/processing. */
export function useReviewPolling(): UseQueryResult<ReviewOut[]> {
  return useQuery({
    queryKey: reviewsQueryKey(),
    queryFn: () => apiClient.request<ReviewOut[]>("/reviews"),
    refetchInterval: (query) => listPollInterval(query.state.data),
  });
}

/** Single-review polling (report page) — stops once that review reaches done/failed. */
export function useReviewStatus(reviewId: string | undefined): UseQueryResult<ReviewOut> {
  return useQuery({
    queryKey: reviewQueryKey(reviewId),
    queryFn: () => apiClient.request<ReviewOut>(`/reviews/${reviewId}`),
    enabled: Boolean(reviewId),
    refetchInterval: (query) => statusPollInterval(query.state.data?.status),
  });
}
