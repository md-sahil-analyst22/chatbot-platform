// ────────────────────────────────────────────────────────────────────────────────────────────
// 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
// What: The one function every page uses to call the backend API.
// Does: Adds the login token, sends the request, and turns error answers into an ApiError the
//       page can show.
// Setting: VITE_API_BASE_URL = the API address (falls back to http://localhost:8000).
// ────────────────────────────────────────────────────────────────────────────────────────────
// From ../auth/token — the login-token holder: getAccessToken = the current login token.
import { getAccessToken } from "../auth/token";

// Where the backend lives.
const BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "http://localhost:8000";

/** Mirrors the backend error model: {"error": {"code", "message", "request_id"}}. */
// An error from the API, with its status, code and request id (handy for support).
export class ApiError extends Error {
  // Created with:
  constructor(
    // the HTTP status (e.g. 404),
    public readonly status: number,
    // our error code (e.g. 'not_found'),
    public readonly code: string,
    // the message to show,
    message: string,
    // and the request id, if the server sent one.
    public readonly requestId?: string,
  ) {
    // Let the built-in Error store the message.
    super(message);
  }
}

// The shape of our API's error answers.
interface ErrorBody {
  // An optional 'error' object with code, message and request id.
  error?: { code?: string; message?: string; request_id?: string };
}

// Does this answer look like our standard error shape?
function isErrorBody(value: unknown): value is ErrorBody {
  // An object that has an 'error' field.
  return typeof value === "object" && value !== null && "error" in value;
}

// Call the API and return its JSON answer (typed as T).
export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  // The current login token.
  const token = getAccessToken();
  // Copy any headers the caller passed.
  const headers = new Headers(init.headers);
  // We always send JSON.
  headers.set("Content-Type", "application/json");
  // 🔒 Logged in? Send the token so the backend knows who is calling.
  if (token) headers.set("Authorization", `Bearer ${token}`);

  // Send the request to <API address><path>.
  const response = await fetch(`${BASE_URL}${path}`, { ...init, headers });
  // Any error status -> throw an ApiError with the backend's message.
  if (!response.ok) {
    // Try to read the error body as JSON (null if it isn't JSON).
    const body: unknown = await response.json().catch(() => null);
    // Our error details, if the body has them.
    const err = isErrorBody(body) ? body.error : undefined;
    // Throw an ApiError with:
    throw new ApiError(
      // the status,
      response.status,
      // our code (or a generic one),
      err?.code ?? "http_error",
      // our message (or the browser's status text),
      err?.message ?? response.statusText,
      // and the request id.
      err?.request_id,
    );
  }
  // 204 = success with no content (e.g. after delete).
  if (response.status === 204) return undefined as T;
  // Otherwise read and return the JSON body.
  return (await response.json()) as T;
}
