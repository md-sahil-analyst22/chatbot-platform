import { describe, expect, it } from "vitest";
import { DEFAULT_CONFIG, botConfigSchema } from "./schema";

describe("botConfigSchema", () => {
  it("accepts the default config", () => {
    expect(botConfigSchema.safeParse(DEFAULT_CONFIG).success).toBe(true);
  });

  it("rejects HTML in widget text", () => {
    const bad = {
      ...DEFAULT_CONFIG,
      branding: { ...DEFAULT_CONFIG.branding, header_title: "<img src=x>" },
    };
    expect(botConfigSchema.safeParse(bad).success).toBe(false);
  });

  it("rejects invalid colour and out-of-range temperature", () => {
    const badColour = {
      ...DEFAULT_CONFIG,
      branding: { ...DEFAULT_CONFIG.branding, primary_color: "red" },
    };
    const hot = {
      ...DEFAULT_CONFIG,
      generation: { ...DEFAULT_CONFIG.generation, temperature_override: 1.5 },
    };
    expect(botConfigSchema.safeParse(badColour).success).toBe(false);
    expect(botConfigSchema.safeParse(hot).success).toBe(false);
  });
});
