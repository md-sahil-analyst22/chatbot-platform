// ────────────────────────────────────────────────────────────────────────────────────────────
// 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
// What: Holds the login token while the page is open.
// Security: 🔒 Kept in memory only (never localStorage), so a malicious script has less to
//           steal.
// ────────────────────────────────────────────────────────────────────────────────────────────
/**
 * Access-token holder. At P1.7 the Supabase Auth / Clerk SDK manages the session and this module
 * returns its current token. Tokens stay in memory (never localStorage) to limit XSS impact.
 */
let accessToken: string | null = null;

// Remember a new token (or null after logging out).
export function setAccessToken(token: string | null): void {
  // Store it.
  accessToken = token;
}

// The current token (null if not logged in).
export function getAccessToken(): string | null {
  // Return it.
  return accessToken;
}
