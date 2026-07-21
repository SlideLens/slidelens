import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { apiClient } from "@/api/client";
import type { Finding } from "@/api/schemas";
import { findings } from "@/fixtures/findings";
import { FindingCard } from "./FindingCard";

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

const finding: Finding = { ...findings[0], user_flag: false, user_like: false };

afterEach(() => {
  vi.restoreAllMocks();
});

describe("FindingCard", () => {
  it("flags the finding via a real request", async () => {
    const requestSpy = vi.spyOn(apiClient, "request").mockResolvedValueOnce(undefined);
    render(<FindingCard finding={finding} />, { wrapper });
    const user = userEvent.setup();

    const flagButton = screen.getByLabelText("Пометить находку как мусорную");
    await user.click(flagButton);

    await waitFor(() =>
      expect(requestSpy).toHaveBeenCalledWith(`/findings/${finding.id}/flag`, { method: "POST" }),
    );
    expect(flagButton).toHaveAttribute("aria-pressed", "true");
  });

  it("likes the finding via a real request", async () => {
    const requestSpy = vi.spyOn(apiClient, "request").mockResolvedValueOnce(undefined);
    render(<FindingCard finding={finding} />, { wrapper });
    const user = userEvent.setup();

    const likeButton = screen.getByLabelText("Пометить находку как полезную");
    await user.click(likeButton);

    await waitFor(() =>
      expect(requestSpy).toHaveBeenCalledWith(`/findings/${finding.id}/like`, { method: "POST" }),
    );
    expect(likeButton).toHaveAttribute("aria-pressed", "true");
  });

  it("shows Apply only for auto_fixable findings", () => {
    const { rerender } = render(
      <FindingCard finding={{ ...finding, auto_fixable: false, auto_fixed: false }} />,
      { wrapper },
    );
    expect(screen.queryByRole("button", { name: "Применить" })).not.toBeInTheDocument();

    rerender(
      <FindingCard finding={{ ...finding, auto_fixable: true, auto_fixed: false }} />,
    );
    expect(screen.getByRole("button", { name: "Применить" })).toBeInTheDocument();
  });

  it("applies a fix via a real request", async () => {
    const requestSpy = vi.spyOn(apiClient, "request").mockResolvedValueOnce(undefined);
    render(<FindingCard finding={{ ...finding, auto_fixable: true, auto_fixed: false }} />, {
      wrapper,
    });
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: "Применить" }));

    await waitFor(() =>
      expect(requestSpy).toHaveBeenCalledWith(`/findings/${finding.id}/apply_fix`, {
        method: "POST",
      }),
    );
    expect(screen.getByRole("button", { name: "Применено" })).toBeDisabled();
  });

  it("does not send a second request once already flagged", async () => {
    const requestSpy = vi.spyOn(apiClient, "request").mockResolvedValue(undefined);
    render(<FindingCard finding={{ ...finding, user_flag: true }} />, { wrapper });
    const user = userEvent.setup();

    await user.click(screen.getByLabelText("Пометить находку как мусорную"));
    expect(requestSpy).not.toHaveBeenCalled();
  });

  it("reverts the flag on request failure", async () => {
    vi.spyOn(apiClient, "request").mockRejectedValueOnce(new Error("network down"));
    render(<FindingCard finding={finding} />, { wrapper });
    const user = userEvent.setup();

    const flagButton = screen.getByLabelText("Пометить находку как мусорную");
    await user.click(flagButton);

    await waitFor(() => expect(flagButton).toHaveAttribute("aria-pressed", "false"));
  });

  describe("interactive=false (демо, без реального API)", () => {
    it("colors like/flag locally without sending a request", async () => {
      const requestSpy = vi.spyOn(apiClient, "request");
      render(<FindingCard finding={finding} interactive={false} />, { wrapper });
      const user = userEvent.setup();

      const likeButton = screen.getByLabelText("Пометить находку как полезную");
      await user.click(likeButton);
      expect(likeButton).toHaveAttribute("aria-pressed", "true");

      const flagButton = screen.getByLabelText("Пометить находку как мусорную");
      await user.click(flagButton);
      expect(flagButton).toHaveAttribute("aria-pressed", "true");
      expect(likeButton).toHaveAttribute("aria-pressed", "false");

      expect(requestSpy).not.toHaveBeenCalled();
    });

    it("applies a fix locally without sending a request", async () => {
      const requestSpy = vi.spyOn(apiClient, "request");
      render(
        <FindingCard
          finding={{ ...finding, auto_fixable: true, auto_fixed: false }}
          interactive={false}
        />,
        { wrapper },
      );
      const user = userEvent.setup();

      await user.click(screen.getByRole("button", { name: "Применить" }));

      expect(screen.getByRole("button", { name: "Применено" })).toBeDisabled();
      expect(requestSpy).not.toHaveBeenCalled();
    });
  });
});
