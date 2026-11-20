// ────────────────────────────────────────────────────────────────────────────────────────────
// 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
// What: Form rules for Bot Studio, checked in the browser for instant feedback.
// Note: 🔒 The backend checks everything again - these rules are a convenience, not the
//       security.
// ────────────────────────────────────────────────────────────────────────────────────────────
// From zod — zod, describes and checks data rules: z = builder for data rules.
import { z } from "zod";

/** Mirrors backend validation (domain/bot_config.py + api/schemas.py). Backend is authoritative. */
// Rule for short widget text: max length and no < or >.
const uiText = (max: number) =>
  // Using zod:
  z
    // it must be text,
    .string()
    // at most `max` characters,
    .max(max, `At most ${max} characters`)
    // and contain no < or >.
    .refine((v) => !/[<>]/.test(v), "Must not contain < or >");

// The rules for the whole config form.
export const botConfigSchema = z.object({
  // The instructions part:
  prompt: z.object({
    // persona: up to 1000 characters,
    persona: z.string().max(1000),
    // brand rules: up to 2000,
    brand_rules: z.string().max(2000),
    // custom instructions: up to 4000,
    custom_instructions: z.string().max(4000),
    // up to 20 banned topics, each 1-100 characters.
    banned_topics: z.array(z.string().min(1).max(100)).max(20),
  }),
  // The model/style part:
  generation: z.object({
    // model key: lowercase letters, digits, dashes,
    model_key: z.string().regex(/^[a-z0-9-]{1,40}$/),
    // one of the three styles,
    style: z.enum(["precise", "balanced", "friendly"]),
    // manual temperature 0-1, or null,
    temperature_override: z.number().min(0).max(1).nullable(),
    // reply length: a whole number from 64 to 2000.
    max_output_tokens: z.number().int().min(64).max(2000),
  }),
  // The look part:
  branding: z.object({
    // title: up to 60 characters, not blank,
    header_title: uiText(60).refine((v) => v.trim().length > 0, "Required"),
    // subtitle: up to 80,
    header_subtitle: uiText(80),
    // footer: up to 120,
    footer_text: uiText(120),
    // greeting: up to 300,
    greeting: uiText(300),
    // colour: #RRGGBB,
    primary_color: z.string().regex(/^#[0-9A-Fa-f]{6}$/, "Use a hex colour like #0F766E"),
    // launcher side: right or left,
    launcher_position: z.enum(["right", "left"]),
    // logo id: a UUID, or null.
    logo_asset_id: z.uuid().nullable(),
  }),
});

// The form's data type, derived from the rules.
export type BotConfigForm = z.infer<typeof botConfigSchema>;

// Starting values for a brand-new bot.
export const DEFAULT_CONFIG: BotConfigForm = {
  // Instructions: all empty.
  prompt: { persona: "", brand_rules: "", custom_instructions: "", banned_topics: [] },
  // Model/style:
  generation: {
    // the standard model,
    model_key: "standard",
    // balanced style,
    style: "balanced",
    // no manual temperature,
    temperature_override: null,
    // 600-token replies.
    max_output_tokens: 600,
  },
  // Look:
  branding: {
    // title,
    header_title: "Chat with us",
    // no subtitle,
    header_subtitle: "",
    // no footer,
    footer_text: "",
    // a friendly greeting,
    greeting: "Hello! How can I help you today?",
    // teal colour,
    primary_color: "#0F766E",
    // launcher on the right,
    launcher_position: "right",
    // no logo.
    logo_asset_id: null,
  },
};
