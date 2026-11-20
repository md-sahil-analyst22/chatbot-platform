// ────────────────────────────────────────────────────────────────────────────────────────────
// 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
// What: TypeScript descriptions of the data the API sends and receives (must match the
//       backend's schemas.py).
// ────────────────────────────────────────────────────────────────────────────────────────────
/**
 * DTOs mirroring backend/src/saathi/modules/tenancy/api/schemas.py.
 * Later: generate these from the backend OpenAPI spec (openapi-typescript) in CI.
 */
export type Language = "en" | "hi" | "bn";
// The three answer styles.
export type ResponseStyle = "precise" | "balanced" | "friendly";
// The three version statuses.
export type ConfigStatus = "draft" | "published" | "archived";

// A bot as the API returns it:
export interface Bot {
  // its id,
  id: string;
  // name,
  name: string;
  // persona,
  persona: string;
  // languages,
  languages: Language[];
  // public widget key,
  public_key: string;
  // extra settings.
  settings: Record<string, unknown>;
}

// The body for creating a bot:
export interface BotCreate {
  // name,
  name: string;
  // languages.
  languages: Language[];
}

// The instructions part of a config:
export interface PromptSettings {
  // persona,
  persona: string;
  // brand rules,
  brand_rules: string;
  // custom instructions,
  custom_instructions: string;
  // topics never to discuss.
  banned_topics: string[];
}

// The model/style part:
export interface GenerationSettings {
  // catalog key,
  model_key: string;
  // answer style,
  style: ResponseStyle;
  // manual temperature (null = use the style),
  temperature_override: number | null;
  // reply length limit.
  max_output_tokens: number;
}

// The look of the widget:
export interface Branding {
  // title,
  header_title: string;
  // subtitle,
  header_subtitle: string;
  // footer,
  footer_text: string;
  // greeting,
  greeting: string;
  // colour,
  primary_color: string;
  // launcher side,
  launcher_position: "right" | "left";
  // logo id (null = none).
  logo_asset_id: string | null;
}

// One complete configuration:
export interface BotConfig {
  // instructions,
  prompt: PromptSettings;
  // model/style,
  generation: GenerationSettings;
  // look.
  branding: Branding;
}

// One saved version:
export interface BotConfigVersion {
  // its number,
  version: number;
  // its status,
  status: ConfigStatus;
  // who saved it,
  created_by: string;
  // when (as text),
  created_at: string;
  // the configuration.
  config: BotConfig;
}

// One choosable model:
export interface ModelOption {
  // its catalog key,
  key: string;
  // its label.
  label: string;
}
