import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import { apiClient } from "@/api/client";
import type { SlideOut } from "@/api/schemas";

/** All rendered slide PNGs for a done Review — powers the rehearsal recorder. */
export function useSlides(reviewId: string | undefined): UseQueryResult<SlideOut[]> {
  return useQuery({
    queryKey: ["slides", reviewId],
    queryFn: () => apiClient.request<SlideOut[]>(`/reviews/${reviewId}/slides`),
    enabled: Boolean(reviewId),
  });
}
