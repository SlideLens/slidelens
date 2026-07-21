import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { apiClient } from "@/api/client";
import type { SlideOut } from "@/api/schemas";
import { RehearsalRecorder } from "./RehearsalRecorder";

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

const slides: SlideOut[] = [
  { slide_num: 1, url: "/files/1?sig=a" },
  { slide_num: 2, url: "/files/2?sig=b" },
  { slide_num: 3, url: "/files/3?sig=c" },
];

class FakeMediaRecorder {
  ondataavailable: ((e: { data: Blob }) => void) | null = null;
  mimeType = "audio/webm";
  stream: MediaStream;
  private listeners: Record<string, (() => void)[]> = {};

  constructor(stream: MediaStream) {
    this.stream = stream;
  }
  start() {}
  stop() {
    this.ondataavailable?.({ data: new Blob(["chunk"]) });
    (this.listeners["stop"] ?? []).forEach((cb) => cb());
  }
  addEventListener(event: string, cb: () => void) {
    this.listeners[event] = [...(this.listeners[event] ?? []), cb];
  }
}

function fakeStream(): MediaStream {
  return { getTracks: () => [{ stop: vi.fn() }] } as unknown as MediaStream;
}

function stubGetUserMedia(impl: () => Promise<MediaStream>) {
  vi.stubGlobal("navigator", {
    ...navigator,
    mediaDevices: { getUserMedia: vi.fn(impl) },
  });
}

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("RehearsalRecorder", () => {
  it("shows an error when microphone access is denied", async () => {
    vi.spyOn(apiClient, "request").mockResolvedValueOnce(slides);
    stubGetUserMedia(() => Promise.reject(new Error("denied")));

    render(<RehearsalRecorder reviewId="r1" onRecorded={vi.fn()} onCancel={vi.fn()} />, { wrapper });
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Начать запись" }));

    expect(
      await screen.findByText(/Не удалось получить доступ к микрофону/),
    ).toBeInTheDocument();
  });

  it("navigates slides with prev/next buttons", async () => {
    vi.spyOn(apiClient, "request").mockResolvedValueOnce(slides);
    render(<RehearsalRecorder reviewId="r1" onRecorded={vi.fn()} onCancel={vi.fn()} />, { wrapper });

    expect(await screen.findByText("Слайд 1 из 3")).toBeInTheDocument();
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Следующий слайд" }));
    expect(await screen.findByText("Слайд 2 из 3")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Предыдущий слайд" }));
    expect(await screen.findByText("Слайд 1 из 3")).toBeInTheDocument();
  });

  it("records and uploads audio + slide timings on stop", async () => {
    vi.spyOn(apiClient, "request").mockResolvedValueOnce(slides);
    stubGetUserMedia(() => Promise.resolve(fakeStream()));
    vi.stubGlobal("MediaRecorder", FakeMediaRecorder);
    const onRecorded = vi.fn();

    render(<RehearsalRecorder reviewId="r1" onRecorded={onRecorded} onCancel={vi.fn()} />, { wrapper });
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Начать запись" }));
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Остановить" })).toBeInTheDocument(),
    );

    const requestSpy = vi.spyOn(apiClient, "request").mockResolvedValueOnce({
      id: "reh-1",
      review_id: "r1",
      status: "queued",
      attempt_num: 1,
      created_at: "2026-01-01T00:00:00Z",
    });

    await user.click(screen.getByRole("button", { name: "Остановить" }));

    await waitFor(() => expect(onRecorded).toHaveBeenCalledWith("reh-1"));
    const [path, options] = requestSpy.mock.calls[0];
    expect(path).toBe("/reviews/r1/rehearsals");
    expect(options?.multipart).toBe(true);
    const body = options?.body as FormData;
    expect(body.get("audio")).toBeInstanceOf(Blob);
    const timings = JSON.parse(body.get("slide_timings") as string);
    expect(timings).toEqual([{ slide_num: 1, start: 0, end: expect.any(Number) }]);
  });
});
