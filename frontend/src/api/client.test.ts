import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiClient } from "./client";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("ApiClient refresh", () => {
  it("refreshes once on 401 and retries the original request", async () => {
    const fetchMock = vi
      .fn()
      // first protected call → 401
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ detail: "expired" }), {
          status: 401,
          headers: { "Content-Type": "application/json" },
        }),
      )
      // refresh
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            access_token: "new-access",
            refresh_token: "new-refresh",
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      )
      // retry
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ status: "ok" }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );

    const client = new ApiClient("/api/v1", fetchMock as unknown as typeof fetch);
    client.setTokens({ access_token: "old-access", refresh_token: "old-refresh" });

    const result = await client.request<{ status: string }>("/health");
    expect(result.status).toBe("ok");
    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(client.getAccessToken()).toBe("new-access");

    const retryHeaders = (fetchMock.mock.calls[2][1] as RequestInit).headers as Record<
      string,
      string
    >;
    expect(retryHeaders.Authorization).toBe("Bearer new-access");
  });

  it("download() returns a Blob and refreshes on 401 like request()", async () => {
    const pdfBytes = new Uint8Array([0x25, 0x50, 0x44, 0x46]); // %PDF
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response(null, { status: 401 }))
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({ access_token: "new-access", refresh_token: "new-refresh" }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(pdfBytes, { status: 200, headers: { "Content-Type": "application/pdf" } }),
      );

    const client = new ApiClient("/api/v1", fetchMock as unknown as typeof fetch);
    client.setTokens({ access_token: "old-access", refresh_token: "old-refresh" });

    const blob = await client.download("/files/abc");
    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(blob.size).toBe(pdfBytes.byteLength);
  });

  it("queues concurrent 401s behind a single refresh", async () => {
    let refreshCalls = 0;
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/auth/refresh")) {
        refreshCalls += 1;
        await new Promise((r) => setTimeout(r, 20));
        return new Response(
          JSON.stringify({ access_token: "shared", refresh_token: "r2" }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      const auth = (init?.headers as Record<string, string> | undefined)?.Authorization;
      if (auth === "Bearer stale") {
        return new Response("{}", { status: 401 });
      }
      return new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    });

    const client = new ApiClient("/api/v1", fetchMock as unknown as typeof fetch);
    client.setTokens({ access_token: "stale", refresh_token: "r1" });

    const [a, b] = await Promise.all([
      client.request<{ ok: boolean }>("/health"),
      client.request<{ ok: boolean }>("/health"),
    ]);
    expect(a.ok && b.ok).toBe(true);
    expect(refreshCalls).toBe(1);
  });
});
