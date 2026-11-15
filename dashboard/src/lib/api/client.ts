import { getAccessToken } from "../auth/token";

const BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "http://localhost:8000";

/** Mirrors the backend error model: {"error": {"code", "message", "request_id"}}. */
export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
    public readonly requestId?: string,
  ) {
    super(message);
  }
}

interface ErrorBody {
  error?: { code?: string; message?: string; request_id?: string };
}

function isErrorBody(value: unknown): value is ErrorBody {
  return typeof value === "object" && value !== null && "error" in value;
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getAccessToken();
  const headers = new Headers(init.headers);
  headers.set("Content-Type", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const response = await fetch(`${BASE_URL}${path}`, { ...init, headers });
  if (!response.ok) {
    const body: unknown = await response.json().catch(() => null);
    const err = isErrorBody(body) ? body.error : undefined;
    throw new ApiError(
      response.status,
      err?.code ?? "http_error",
      err?.message ?? response.statusText,
      err?.request_id,
    );
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}
