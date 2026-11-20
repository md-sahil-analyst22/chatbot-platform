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
export type ResponseStyle = "precise" | "balanced" | "friendly";
export type ConfigStatus = "draft" | "published" | "archived";

export interface Bot {
  id: string;
  name: string;
  persona: string;
  languages: Language[];
  public_key: string;
  settings: Record<string, unknown>;
}

export interface BotCreate {
  name: string;
  languages: Language[];
}

export interface PromptSettings {
  persona: string;
  brand_rules: string;
  custom_instructions: string;
  banned_topics: string[];
}

export interface GenerationSettings {
  model_key: string;
  style: ResponseStyle;
  temperature_override: number | null;
  max_output_tokens: number;
}

export interface Branding {
  header_title: string;
  header_subtitle: string;
  footer_text: string;
  greeting: string;
  primary_color: string;
  launcher_position: "right" | "left";
  logo_asset_id: string | null;
}

export interface BotConfig {
  prompt: PromptSettings;
  generation: GenerationSettings;
  branding: Branding;
}

export interface BotConfigVersion {
  version: number;
  status: ConfigStatus;
  created_by: string;
  created_at: string;
  config: BotConfig;
}

export interface ModelOption {
  key: string;
  label: string;
}
