// ────────────────────────────────────────────────────────────────────────────────────────────
// 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
// What: The answer-style choices shown in Bot Studio (precise, balanced, friendly) with help
//       text.
// ────────────────────────────────────────────────────────────────────────────────────────────
import type { ResponseStyle } from "../../lib/api/types";

/** Plain-language presets for non-technical users. Temperatures match the backend. */
export const STYLE_PRESETS: { value: ResponseStyle; label: string; help: string }[] = [
  { value: "precise", label: "Precise", help: "Sticks closely to your documents. Best for prices and policies." },
  { value: "balanced", label: "Balanced", help: "Accurate with a natural tone. Recommended." },
  { value: "friendly", label: "Friendly", help: "Warmer, more conversational wording." },
];
