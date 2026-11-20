// ────────────────────────────────────────────────────────────────────────────────────────────
// 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
// What: Hooks for Bot Studio: load the draft/versions/models, save a draft, publish, roll back.
// Refresh: After every change the cached config data is marked stale, so the screen reloads it.
// ────────────────────────────────────────────────────────────────────────────────────────────
// From @tanstack/react-query — React Query, loads and caches data from the API: useMutation =
//   sends a change to the API; useQuery = loads data from the API; useQueryClient = access to the
//   data cache.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
// From ../../lib/api/client — the API caller: ApiError = an error answer from the API; api =
//   calls the API.
import { ApiError, api } from "../../lib/api/client";
// From ../../lib/api/types — the API data types: BotConfig = config type; BotConfigVersion
//   = version type; ModelOption = model option type.
import type { BotConfig, BotConfigVersion, ModelOption } from "../../lib/api/types";

// Base address of one bot's config endpoints.
const base = (botId: string) => `/api/v1/bots/${botId}/config`;

// Load the newest draft (none yet = start from defaults).
export function useDraft(botId: string) {
  // Load the draft:
  return useQuery({
    // cached under ['config', botId, 'draft'],
    queryKey: ["config", botId, "draft"],
    // fetched by:
    queryFn: async () => {
      // trying GET .../config/draft;
      try {
        // (return the draft)
        return await api<BotConfigVersion>(`${base(botId)}/draft`);
      // if that fails:
      } catch (e) {
        if (e instanceof ApiError && e.status === 404) return null; // new bot: no draft yet
        // any other error is passed on.
        throw e;
      }
    },
  });
}

// Load the version history.
export function useVersions(botId: string) {
  // Load the version history:
  return useQuery({
    // cached under ['config', botId, 'versions'],
    queryKey: ["config", botId, "versions"],
    // fetched with GET .../config/versions?limit=20.
    queryFn: () => api<BotConfigVersion[]>(`${base(botId)}/versions?limit=20`),
  });
}

// Load the models your plan allows.
export function useModelOptions() {
  // Load GET /api/v1/model-options, cached under 'model-options'.
  return useQuery({ queryKey: ["model-options"], queryFn: () => api<ModelOption[]>("/api/v1/model-options") });
}

// Helper: mark this bot's config data as stale.
function useInvalidate(botId: string) {
  // Access to the data cache.
  const queryClient = useQueryClient();
  // A function that marks everything cached for this bot's config as stale.
  return () => queryClient.invalidateQueries({ queryKey: ["config", botId] });
}

// Save the form as a new draft version.
export function useSaveDraft(botId: string) {
  // The 'mark stale' function for this bot.
  const invalidate = useInvalidate(botId);
  // Return a mutation:
  return useMutation({
    // it sends the config...
    mutationFn: (config: BotConfig) =>
      // ...as POST .../config/versions;
      api<BotConfigVersion>(`${base(botId)}/versions`, { method: "POST", body: JSON.stringify(config) }),
    // afterwards: reload this bot's config data.
    onSuccess: invalidate,
  });
}

// Make a version live.
export function usePublish(botId: string) {
  // The 'mark stale' function.
  const invalidate = useInvalidate(botId);
  // Return a mutation:
  return useMutation({
    // it takes a version number...
    mutationFn: (version: number) =>
      // ...and sends POST .../versions/<n>/publish;
      api<BotConfigVersion>(`${base(botId)}/versions/${version}/publish`, { method: "POST" }),
    // afterwards: reload this bot's config data.
    onSuccess: invalidate,
  });
}

// Go back to an old version.
export function useRollback(botId: string) {
  // The 'mark stale' function.
  const invalidate = useInvalidate(botId);
  // Return a mutation:
  return useMutation({
    // it takes a version number...
    mutationFn: (version: number) =>
      // ...and sends POST .../versions/<n>/rollback;
      api<BotConfigVersion>(`${base(botId)}/versions/${version}/rollback`, { method: "POST" }),
    // afterwards: reload this bot's config data.
    onSuccess: invalidate,
  });
}
