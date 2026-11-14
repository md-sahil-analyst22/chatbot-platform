import { z } from "zod";

/** Mirrors backend validation (domain/bot_config.py + api/schemas.py). Backend is authoritative. */
const uiText = (max: number) =>
  z
    .string()
    .max(max, `At most ${max} characters`)
    .refine((v) => !/[<>]/.test(v), "Must not contain < or >");

export const botConfigSchema = z.object({
  prompt: z.object({
    persona: z.string().max(1000),
    brand_rules: z.string().max(2000),
    custom_instructions: z.string().max(4000),
    banned_topics: z.array(z.string().min(1).max(100)).max(20),
  }),
  generation: z.object({
    model_key: z.string().regex(/^[a-z0-9-]{1,40}$/),
    style: z.enum(["precise", "balanced", "friendly"]),
    temperature_override: z.number().min(0).max(1).nullable(),
    max_output_tokens: z.number().int().min(64).max(2000),
  }),
  branding: z.object({
    header_title: uiText(60).refine((v) => v.trim().length > 0, "Required"),
    header_subtitle: uiText(80),
    footer_text: uiText(120),
    greeting: uiText(300),
    primary_color: z.string().regex(/^#[0-9A-Fa-f]{6}$/, "Use a hex colour like #0F766E"),
    launcher_position: z.enum(["right", "left"]),
    logo_asset_id: z.uuid().nullable(),
  }),
});

export type BotConfigForm = z.infer<typeof botConfigSchema>;

export const DEFAULT_CONFIG: BotConfigForm = {
  prompt: { persona: "", brand_rules: "", custom_instructions: "", banned_topics: [] },
  generation: {
    model_key: "standard",
    style: "balanced",
    temperature_override: null,
    max_output_tokens: 600,
  },
  branding: {
    header_title: "Chat with us",
    header_subtitle: "",
    footer_text: "",
    greeting: "Hello! How can I help you today?",
    primary_color: "#0F766E",
    launcher_position: "right",
    logo_asset_id: null,
  },
};
