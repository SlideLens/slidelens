import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/api/client";

/** POST /findings/{id}/like — 👍; clears user_flag on the server. */
export function useLikeFinding(reviewId?: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (findingId: string) =>
      apiClient.request<void>(`/findings/${findingId}/like`, { method: "POST" }),
    onSuccess: () => {
      if (reviewId) {
        void queryClient.invalidateQueries({ queryKey: ["report", reviewId] });
      }
    },
  });
}
