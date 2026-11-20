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
  return useQuery({
    queryKey: ["config", botId, "draft"],
    queryFn: async () => {
      try {
        return await api<BotConfigVersion>(`${base(botId)}/draft`);
      } catch (e) {
        if (e instanceof ApiError && e.status === 404) return null; // new bot: no draft yet
        throw e;
      }
    },
  });
}

// Load the version history.
export function useVersions(botId: string) {
  return useQuery({
    queryKey: ["config", botId, "versions"],
    queryFn: () => api<BotConfigVersion[]>(`${base(botId)}/versions?limit=20`),
  });
}

// Load the models your plan allows.
export function useModelOptions() {
  return useQuery({ queryKey: ["model-options"], queryFn: () => api<ModelOption[]>("/api/v1/model-options") });
}

// Helper: mark this bot's config data as stale.
function useInvalidate(botId: string) {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: ["config", botId] });
}

// Save the form as a new draft version.
export function useSaveDraft(botId: string) {
  const invalidate = useInvalidate(botId);
  return useMutation({
    mutationFn: (config: BotConfig) =>
      api<BotConfigVersion>(`${base(botId)}/versions`, { method: "POST", body: JSON.stringify(config) }),
    onSuccess: invalidate,
  });
}

// Make a version live.
export function usePublish(botId: string) {
  const invalidate = useInvalidate(botId);
  return useMutation({
    mutationFn: (version: number) =>
      api<BotConfigVersion>(`${base(botId)}/versions/${version}/publish`, { method: "POST" }),
    onSuccess: invalidate,
  });
}

// Go back to an old version.
export function useRollback(botId: string) {
  const invalidate = useInvalidate(botId);
  return useMutation({
    mutationFn: (version: number) =>
      api<BotConfigVersion>(`${base(botId)}/versions/${version}/rollback`, { method: "POST" }),
    onSuccess: invalidate,
  });
}
