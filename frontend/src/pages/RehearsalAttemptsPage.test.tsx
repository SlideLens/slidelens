import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { apiClient } from "@/api/client";
import type { RehearsalOut, ReviewOut } from "@/api/schemas";
import RehearsalAttemptsPage from "./RehearsalAttemptsPage";

function renderAt(reviewId: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[`/rehearsal/${reviewId}`]}>
        <Routes>
          <Route path="/rehearsal/:reviewId" element={<RehearsalAttemptsPage />} />
          <Route path="/rehearsal/:reviewId/new" element={<div>Record page</div>} />
          <Route
            path="/rehearsal/:reviewId/attempts/:rehearsalId"
            element={<div>Attempt report page</div>}
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const review: ReviewOut = {
  id: "r1",
  status: "done",
  score: 88,
  deck_filename: "pitch.pptx",
  n_slides: 5,
  has_audio: false,
  has_data: false,
  created_at: "2026-01-01T00:00:00Z",
};

const attempts: RehearsalOut[] = [
  { id: "reh-1", review_id: "r1", status: "done", attempt_num: 1, created_at: "2026-01-01T00:00:00Z" },
  { id: "reh-2", review_id: "r1", status: "failed", attempt_num: 2, created_at: "2026-01-02T00:00:00Z" },
];

afterEach(() => {
  vi.restoreAllMocks();
});

describe("RehearsalAttemptsPage", () => {
  it("shows the empty state when there are no attempts yet", async () => {
    vi.spyOn(apiClient, "request").mockResolvedValueOnce(review).mockResolvedValueOnce([]);
    renderAt("r1");

    expect(await screen.findByText("Пока нет попыток")).toBeInTheDocument();
  });

  it("lists past attempts with status, newest first, and links to each report", async () => {
    vi.spyOn(apiClient, "request").mockResolvedValueOnce(review).mockResolvedValueOnce(attempts);
    renderAt("r1");

    expect(await screen.findByText("Попытка №2")).toBeInTheDocument();
    expect(screen.getByText("Попытка №1")).toBeInTheDocument();
    expect(screen.getByText("Готово")).toBeInTheDocument();
    expect(screen.getByText("Ошибка")).toBeInTheDocument();

    const user = userEvent.setup();
    await user.click(screen.getByText("Попытка №1"));
    expect(await screen.findByText("Attempt report page")).toBeInTheDocument();
  });

  it("navigates to the recorder when starting a new attempt", async () => {
    vi.spyOn(apiClient, "request").mockResolvedValueOnce(review).mockResolvedValueOnce(attempts);
    renderAt("r1");

    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: /Записать новую попытку/ }));
    expect(await screen.findByText("Record page")).toBeInTheDocument();
  });

  it("requires confirmation before deleting an attempt", async () => {
    vi.spyOn(apiClient, "request").mockResolvedValueOnce(review).mockResolvedValueOnce(attempts);
    renderAt("r1");
    await screen.findByText("Попытка №1");

    const user = userEvent.setup();
    await user.click(screen.getAllByRole("button", { name: "Удалить попытку" })[0]);

    expect(screen.getByText("Удалить?")).toBeInTheDocument();
    // still present — nothing deleted yet, no confirming request sent
    expect(screen.getByText("Попытка №2")).toBeInTheDocument();
  });

  it("deletes the attempt after confirming", async () => {
    const requestSpy = vi
      .spyOn(apiClient, "request")
      .mockResolvedValueOnce(review)
      .mockResolvedValueOnce(attempts)
      .mockResolvedValueOnce(undefined) // DELETE
      .mockResolvedValueOnce([attempts[1]]); // refetch after invalidation

    renderAt("r1");
    await screen.findByText("Попытка №2");

    const user = userEvent.setup();
    await user.click(screen.getAllByRole("button", { name: "Удалить попытку" })[0]);
    await user.click(screen.getByRole("button", { name: "Да" }));

    const deleteCall = requestSpy.mock.calls.find(([, options]) => options?.method === "DELETE");
    expect(deleteCall?.[0]).toBe("/rehearsals/reh-2");
  });

  it("cancels the delete confirmation without deleting", async () => {
    vi.spyOn(apiClient, "request").mockResolvedValueOnce(review).mockResolvedValueOnce(attempts);
    renderAt("r1");
    await screen.findByText("Попытка №2");

    const user = userEvent.setup();
    await user.click(screen.getAllByRole("button", { name: "Удалить попытку" })[0]);
    await user.click(screen.getByRole("button", { name: "Нет" }));

    expect(screen.queryByText("Удалить?")).not.toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "Удалить попытку" })).toHaveLength(2);
  });
});
