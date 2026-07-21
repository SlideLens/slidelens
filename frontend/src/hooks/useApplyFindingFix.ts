import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/api/client";

/** POST /findings/{id}/apply_fix — regenerate fixed.pptx for this finding. */
export function useApplyFindingFix(reviewId?: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (findingId: string) =>
      apiClient.request<void>(`/findings/${findingId}/apply_fix`, { method: "POST" }),
    onSuccess: () => {
      if (reviewId) {
        void queryClient.invalidateQueries({ queryKey: ["report", reviewId] });
      }
    },
  });
}
