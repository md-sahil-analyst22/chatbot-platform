// ────────────────────────────────────────────────────────────────────────────────────────────
// 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
// What: The one function every page uses to call the backend API.
// Does: Adds the login token, sends the request, and turns error answers into an ApiError the
//       page can show.
// Setting: VITE_API_BASE_URL = the API address (falls back to http://localhost:8000).
// ────────────────────────────────────────────────────────────────────────────────────────────
import { getAccessToken } from "../auth/token";

// Where the backend lives.
const BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "http://localhost:8000";

/** Mirrors the backend error model: {"error": {"code", "message", "request_id"}}. */
// An error from the API, with its status, code and request id (handy for support).
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

// Does this answer look like our standard error shape?
function isErrorBody(value: unknown): value is ErrorBody {
  return typeof value === "object" && value !== null && "error" in value;
}

// Call the API and return its JSON answer (typed as T).
export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getAccessToken();
  const headers = new Headers(init.headers);
  headers.set("Content-Type", "application/json");
  // 🔒 Logged in? Send the token so the backend knows who is calling.
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const response = await fetch(`${BASE_URL}${path}`, { ...init, headers });
  // Any error status -> throw an ApiError with the backend's message.
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
  // 204 = success with no content (e.g. after delete).
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}
