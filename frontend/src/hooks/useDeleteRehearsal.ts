import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/api/client";
import { rehearsalsQueryKey } from "@/hooks/useRehearsalPolling";

/** DELETE /rehearsals/{id} — removes the attempt and its stored audio. */
export function useDeleteRehearsal(reviewId?: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (rehearsalId: string) =>
      apiClient.request<void>(`/rehearsals/${rehearsalId}`, { method: "DELETE" }),
    onSuccess: () => {
      if (reviewId) {
        void queryClient.invalidateQueries({ queryKey: rehearsalsQueryKey(reviewId) });
      }
    },
  });
}
