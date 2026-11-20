// ────────────────────────────────────────────────────────────────────────────────────────────
// 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
// What: The answer-style choices shown in Bot Studio (precise, balanced, friendly) with help
//       text.
// ────────────────────────────────────────────────────────────────────────────────────────────
// From ../../lib/api/types — the API data types: ResponseStyle = precise/balanced/friendly
//   type.
import type { ResponseStyle } from "../../lib/api/types";

/** Plain-language presets for non-technical users. Temperatures match the backend. */
export const STYLE_PRESETS: { value: ResponseStyle; label: string; help: string }[] = [
  // Precise: sticks to the documents.
  { value: "precise", label: "Precise", help: "Sticks closely to your documents. Best for prices and policies." },
  // Balanced: the recommended middle ground.
  { value: "balanced", label: "Balanced", help: "Accurate with a natural tone. Recommended." },
  // Friendly: warmer wording.
  { value: "friendly", label: "Friendly", help: "Warmer, more conversational wording." },
];
