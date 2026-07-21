import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { apiClient, ApiError } from "@/api/client";
import { UploadDropzone } from "./UploadDropzone";

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return (
    <QueryClientProvider client={client}>
      <MemoryRouter>{children}</MemoryRouter>
    </QueryClientProvider>
  );
}

function renderDropzone() {
  return render(<UploadDropzone />, { wrapper });
}

function deckFile(name = "deck.pptx", sizeBytes = 1024): File {
  return new File([new Uint8Array(sizeBytes)], name, {
    type: "application/vnd.openxmlformats-officedocument.presentationml.presentation",
  });
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("UploadDropzone", () => {
  it("rejects a wrong-format deck before sending a request", async () => {
    const requestSpy = vi.spyOn(apiClient, "request");
    renderDropzone();
    // The real browser already filters the file picker by `accept`; this test is about
    // *our* validation message, so bypass user-event's own accept-based filtering.
    const user = userEvent.setup({ applyAccept: false });
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;

    await user.upload(input, deckFile("deck.key"));

    expect(await screen.findByText("Дека должна быть в формате .pptx или .pdf")).toBeInTheDocument();
    expect(requestSpy).not.toHaveBeenCalled();
  });

  it("uploads successfully and shows the queued confirmation", async () => {
    vi.spyOn(apiClient, "request").mockResolvedValueOnce({
      id: "r1",
      status: "queued",
      deck_filename: "deck.pptx",
      has_audio: false,
      has_data: false,
      created_at: "2026-01-01T00:00:00Z",
    });
    renderDropzone();
    const user = userEvent.setup();
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;

    await user.upload(input, deckFile());
    await user.click(screen.getByRole("button", { name: "Запустить Разбор" }));

    expect(
      await screen.findByText("Дека загружена — Разбор поставлен в очередь."),
    ).toBeInTheDocument();
  });

  it("shows the 402 limit message on failure", async () => {
    vi.spyOn(apiClient, "request").mockRejectedValueOnce(
      new ApiError(402, "Закончились доступные Разборы — пополните баланс", null),
    );
    renderDropzone();
    const user = userEvent.setup();
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;

    await user.upload(input, deckFile());
    await user.click(screen.getByRole("button", { name: "Запустить Разбор" }));

    expect(await screen.findByText(/Закончились доступные Разборы/)).toBeInTheDocument();
    // Ошибка должна вести на тарифы, а не быть тупиком.
    expect(screen.getByRole("link", { name: "Посмотреть тарифы" })).toHaveAttribute(
      "href",
      "/pricing",
    );
    expect(
      screen.queryByText("Дека загружена — Разбор поставлен в очередь."),
    ).not.toBeInTheDocument();
  });

  it("sends deck/audio/data as multipart fields", async () => {
    const requestSpy = vi.spyOn(apiClient, "request").mockResolvedValueOnce({
      id: "r1",
      status: "queued",
      deck_filename: "deck.pptx",
      has_audio: false,
      has_data: false,
      created_at: "2026-01-01T00:00:00Z",
    });
    renderDropzone();
    const user = userEvent.setup();
    const deckInput = document.querySelector('input[type="file"]') as HTMLInputElement;

    await user.upload(deckInput, deckFile());
    await user.click(screen.getByRole("button", { name: "Запустить Разбор" }));

    await waitFor(() => expect(requestSpy).toHaveBeenCalledTimes(1));
    const [path, options] = requestSpy.mock.calls[0];
    expect(path).toBe("/reviews");
    expect(options?.method).toBe("POST");
    expect(options?.multipart).toBe(true);
    const body = options?.body as FormData;
    expect(body.get("deck")).toBeInstanceOf(File);
  });
});
