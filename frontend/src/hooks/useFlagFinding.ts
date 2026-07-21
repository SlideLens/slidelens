import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/api/client";

/** POST /findings/{id}/flag — 👎; clears user_like on the server. */
export function useFlagFinding(reviewId?: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (findingId: string) =>
      apiClient.request<void>(`/findings/${findingId}/flag`, { method: "POST" }),
    onSuccess: () => {
      if (reviewId) {
        void queryClient.invalidateQueries({ queryKey: ["report", reviewId] });
      }
    },
  });
}
