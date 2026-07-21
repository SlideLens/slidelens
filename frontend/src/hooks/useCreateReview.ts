import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/api/client";
import type { ReviewOut } from "@/api/schemas";
import { reviewsQueryKey } from "@/hooks/useReviewPolling";

export interface CreateReviewInput {
  deck: File;
  audio?: File | null;
  data?: File | null;
}

export function useCreateReview() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (input: CreateReviewInput) => {
      const formData = new FormData();
      formData.append("deck", input.deck);
      if (input.audio) formData.append("audio", input.audio);
      if (input.data) formData.append("data", input.data);
      return apiClient.request<ReviewOut>("/reviews", {
        method: "POST",
        body: formData,
        multipart: true,
      });
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: reviewsQueryKey() });
    },
  });
}
