import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/api/client";
import type { RehearsalOut, SlideTimingIn } from "@/api/schemas";

export interface CreateRehearsalInput {
  reviewId: string;
  audio: Blob;
  audioFilename: string;
  slideTimings: SlideTimingIn[];
}

export function useCreateRehearsal() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ reviewId, audio, audioFilename, slideTimings }: CreateRehearsalInput) => {
      const formData = new FormData();
      formData.append("audio", audio, audioFilename);
      formData.append("slide_timings", JSON.stringify(slideTimings));
      return apiClient.request<RehearsalOut>(`/reviews/${reviewId}/rehearsals`, {
        method: "POST",
        body: formData,
        multipart: true,
      });
    },
    onSuccess: (_data, { reviewId }) => {
      void queryClient.invalidateQueries({ queryKey: ["rehearsals", reviewId] });
    },
  });
}
