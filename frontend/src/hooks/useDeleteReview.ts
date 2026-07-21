import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/api/client";
import { reviewsQueryKey } from "@/hooks/useReviewPolling";

/** DELETE /reviews/{id} — removes the Разбор, its files, Находки, and all rehearsal attempts. */
export function useDeleteReview() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (reviewId: string) =>
      apiClient.request<void>(`/reviews/${reviewId}`, { method: "DELETE" }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: reviewsQueryKey() });
    },
  });
}
