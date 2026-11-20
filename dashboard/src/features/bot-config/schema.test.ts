// ────────────────────────────────────────────────────────────────────────────────────────────
// 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
// What it tests: The Bot Studio form rules (defaults accepted, bad values refused).
// How to run: cd dashboard && npm test
// ────────────────────────────────────────────────────────────────────────────────────────────
// From vitest — the test framework: describe = groups tests; expect = checks a result; it = one
//   test.
import { describe, expect, it } from "vitest";
// From ./schema — the Bot Studio form rules: DEFAULT_CONFIG = starting values; botConfigSchema
//   = the form rules.
import { DEFAULT_CONFIG, botConfigSchema } from "./schema";

// A group of tests for the form rules.
describe("botConfigSchema", () => {
  // Test: the default values pass the rules.
  it("accepts the default config", () => {
    // safeParse checks without throwing; `success` must be true.
    expect(botConfigSchema.safeParse(DEFAULT_CONFIG).success).toBe(true);
  });

  // Test: HTML in widget text is refused.
  it("rejects HTML in widget text", () => {
    // The defaults...
    const bad = {
      // (all default values)
      ...DEFAULT_CONFIG,
      // ...with an <img> tag as the title.
      branding: { ...DEFAULT_CONFIG.branding, header_title: "<img src=x>" },
    };
    // Must fail.
    expect(botConfigSchema.safeParse(bad).success).toBe(false);
  });

  // Test: a bad colour and a too-high temperature are refused.
  it("rejects invalid colour and out-of-range temperature", () => {
    // The defaults...
    const badColour = {
      // (all default values)
      ...DEFAULT_CONFIG,
      // ...with 'red' as the colour.
      branding: { ...DEFAULT_CONFIG.branding, primary_color: "red" },
    };
    // The defaults...
    const hot = {
      // (all default values)
      ...DEFAULT_CONFIG,
      // ...with temperature 1.5.
      generation: { ...DEFAULT_CONFIG.generation, temperature_override: 1.5 },
    };
    // The bad colour must fail.
    expect(botConfigSchema.safeParse(badColour).success).toBe(false);
    // The high temperature must fail.
    expect(botConfigSchema.safeParse(hot).success).toBe(false);
  });
});
