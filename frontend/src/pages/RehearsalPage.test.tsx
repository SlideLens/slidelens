import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { apiClient } from "@/api/client";
import type { ReviewOut } from "@/api/schemas";
import RehearsalPage from "./RehearsalPage";

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/rehearsal"]}>
        <Routes>
          <Route path="/rehearsal" element={<RehearsalPage />} />
          <Route path="/rehearsal/:reviewId" element={<div>Attempts page for r1</div>} />
          <Route path="/rehearsal/:reviewId/new" element={<div>Record page for r1</div>} />
          <Route path="/cabinet" element={<div>Cabinet page</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const doneReview: ReviewOut = {
  id: "r1",
  status: "done",
  score: 88,
  deck_filename: "pitch.pptx",
  n_slides: 5,
  has_audio: false,
  has_data: false,
  created_at: "2026-01-01T00:00:00Z",
};

const processingReview: ReviewOut = {
  id: "r2",
  status: "processing",
  deck_filename: "other.pptx",
  n_slides: null,
  has_audio: false,
  has_data: false,
  created_at: "2026-01-01T00:00:00Z",
};

afterEach(() => {
  vi.restoreAllMocks();
});

describe("RehearsalPage", () => {
  it("shows the empty state when there are no done reviews", async () => {
    vi.spyOn(apiClient, "request").mockResolvedValueOnce([processingReview]);
    renderPage();

    expect(await screen.findByText("Пока нет готовых Разборов")).toBeInTheDocument();
  });

  it("links to the cabinet to upload a new deck instead of duplicating the dropzone", async () => {
    vi.spyOn(apiClient, "request").mockResolvedValueOnce([doneReview]);
    renderPage();

    await screen.findByText("pitch.pptx");
    expect(screen.queryByText("Перетащите файл сюда или нажмите, чтобы его выбрать")).not.toBeInTheDocument();

    const user = userEvent.setup();
    await user.click(screen.getByRole("link", { name: /Загрузить новую Деку/ }));

    expect(await screen.findByText("Cabinet page")).toBeInTheDocument();
  });

  it("lists only done reviews for rehearsal", async () => {
    vi.spyOn(apiClient, "request").mockResolvedValueOnce([doneReview, processingReview]);
    renderPage();

    expect(await screen.findByText("pitch.pptx")).toBeInTheDocument();
    expect(screen.queryByText("other.pptx")).not.toBeInTheDocument();
  });

  it("navigates to the review's attempts page via the history button", async () => {
    vi.spyOn(apiClient, "request").mockResolvedValueOnce([doneReview]);
    renderPage();

    const user = userEvent.setup();
    await screen.findByText("pitch.pptx");
    await user.click(screen.getByRole("button", { name: /Все попытки/ }));

    expect(await screen.findByText("Attempts page for r1")).toBeInTheDocument();
  });

  it("navigates straight to the recorder via the record button", async () => {
    vi.spyOn(apiClient, "request").mockResolvedValueOnce([doneReview]);
    renderPage();

    const user = userEvent.setup();
    await screen.findByText("pitch.pptx");
    await user.click(screen.getByRole("button", { name: /Записать репетицию/ }));

    expect(await screen.findByText("Record page for r1")).toBeInTheDocument();
  });

  it("requires confirmation before deleting a deck card", async () => {
    vi.spyOn(apiClient, "request").mockResolvedValueOnce([doneReview]);
    renderPage();

    const user = userEvent.setup();
    await screen.findByText("pitch.pptx");
    await user.click(screen.getByRole("button", { name: "Удалить Деку" }));

    expect(await screen.findByText("Удалить «pitch.pptx»?")).toBeInTheDocument();
    expect(
      screen.getByText(/Пропадёт весь Разбор, скачанные файлы и все попытки репетиции/),
    ).toBeInTheDocument();
  });

  it("deletes the deck after confirming", async () => {
    const requestSpy = vi
      .spyOn(apiClient, "request")
      .mockResolvedValueOnce([doneReview])
      .mockResolvedValueOnce(undefined) // DELETE
      .mockResolvedValueOnce([]); // refetch after invalidation

    renderPage();
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Удалить Деку" }));
    await user.click(screen.getByRole("button", { name: "Да, удалить" }));

    const deleteCall = requestSpy.mock.calls.find(([, options]) => options?.method === "DELETE");
    expect(deleteCall?.[0]).toBe("/reviews/r1");
  });

  it("cancels the delete confirmation without deleting", async () => {
    vi.spyOn(apiClient, "request").mockResolvedValueOnce([doneReview]);
    renderPage();

    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Удалить Деку" }));
    await user.click(screen.getByRole("button", { name: "Отмена" }));

    expect(screen.queryByText(/Удалить «pitch\.pptx»\?/)).not.toBeInTheDocument();
    expect(screen.getByText("pitch.pptx")).toBeInTheDocument();
  });
});
