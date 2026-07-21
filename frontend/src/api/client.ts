export type TokenPair = {
  access_token: string;
  refresh_token: string;
};

export type ApiErrorBody = {
  detail?: string | { msg?: string }[];
  message?: string;
};

export class ApiError extends Error {
  readonly status: number;
  readonly body: unknown;

  constructor(status: number, message: string, body: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

export function mapApiError(status: number, body: unknown): string {
  if (body && typeof body === "object") {
    const typed = body as ApiErrorBody;
    if (typeof typed.detail === "string") return typed.detail;
    if (Array.isArray(typed.detail) && typed.detail[0]?.msg) return typed.detail[0].msg;
    if (typeof typed.message === "string") return typed.message;
  }
  if (status === 401) return "Требуется вход в аккаунт";
  if (status === 403) return "Недостаточно прав";
  if (status === 404) return "Не найдено";
  if (status === 409) return "Конфликт данных";
  if (status >= 500) return "Сервер временно недоступен";
  return `Ошибка запроса (${status})`;
}

type RequestOptions = {
  method?: string;
  body?: unknown;
  headers?: Record<string, string>;
  auth?: boolean;
  multipart?: boolean;
  _retry?: boolean;
};

export class ApiClient {
  private accessToken: string | null = null;
  private refreshToken: string | null = null;
  private refreshPromise: Promise<boolean> | null = null;
  private onTokensChange: ((tokens: TokenPair | null) => void) | null = null;

  constructor(
    private readonly baseUrl: string = "/api/v1",
    // Bind to globalThis — bare `fetch` as a method ref throws Illegal invocation in browsers.
    private readonly fetchImpl: typeof fetch = globalThis.fetch.bind(globalThis),
  ) {}

  /** Called on every setTokens() — including the internal 401-refresh path. */
  setOnTokensChange(listener: ((tokens: TokenPair | null) => void) | null): void {
    this.onTokensChange = listener;
  }

  setTokens(tokens: TokenPair | null): void {
    this.accessToken = tokens?.access_token ?? null;
    this.refreshToken = tokens?.refresh_token ?? null;
    this.onTokensChange?.(tokens);
  }

  getAccessToken(): string | null {
    return this.accessToken;
  }

  /** Shared fetch + 401-refresh-retry + error-throw path for request() and download(). */
  private async fetchWithAuth(path: string, options: RequestOptions = {}): Promise<Response> {
    const {
      method = "GET",
      body,
      headers = {},
      auth = true,
      multipart = false,
      _retry = false,
    } = options;

    const reqHeaders: Record<string, string> = { ...headers };
    if (auth && this.accessToken) {
      reqHeaders.Authorization = `Bearer ${this.accessToken}`;
    }

    let payload: BodyInit | undefined;
    if (body !== undefined) {
      if (multipart) {
        payload = body as BodyInit;
      } else {
        reqHeaders["Content-Type"] = "application/json";
        payload = JSON.stringify(body);
      }
    }

    const response = await this.fetchImpl(`${this.baseUrl}${path}`, {
      method,
      headers: reqHeaders,
      body: payload,
    });

    if (response.status === 401 && auth && !_retry) {
      const refreshed = await this.refreshAccessToken();
      if (refreshed) {
        return this.fetchWithAuth(path, { ...options, _retry: true });
      }
    }

    if (!response.ok) {
      let parsed: unknown = null;
      try {
        parsed = await response.json();
      } catch {
        parsed = null;
      }
      throw new ApiError(response.status, mapApiError(response.status, parsed), parsed);
    }

    return response;
  }

  async request<T>(path: string, options: RequestOptions = {}): Promise<T> {
    const response = await this.fetchWithAuth(path, options);
    if (response.status === 204) {
      return undefined as T;
    }
    return (await response.json()) as T;
  }

  /** Binary downloads (PDF/pptx) — same auth/refresh path as request(), returns a Blob. */
  async download(path: string, options: RequestOptions = {}): Promise<Blob> {
    const response = await this.fetchWithAuth(path, options);
    return response.blob();
  }

  private async refreshAccessToken(): Promise<boolean> {
    if (!this.refreshToken) return false;
    if (this.refreshPromise) return this.refreshPromise;

    this.refreshPromise = (async () => {
      try {
        const response = await this.fetchImpl(`${this.baseUrl}/auth/refresh`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refresh_token: this.refreshToken }),
        });
        if (!response.ok) {
          this.setTokens(null);
          return false;
        }
        const data = (await response.json()) as TokenPair;
        this.setTokens(data);
        return true;
      } catch {
        this.setTokens(null);
        return false;
      } finally {
        this.refreshPromise = null;
      }
    })();

    return this.refreshPromise;
  }
}

export const apiClient = new ApiClient();
