import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, api } from "../../lib/api/client";
import type { BotConfig, BotConfigVersion, ModelOption } from "../../lib/api/types";

const base = (botId: string) => `/api/v1/bots/${botId}/config`;

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

export function useVersions(botId: string) {
  return useQuery({
    queryKey: ["config", botId, "versions"],
    queryFn: () => api<BotConfigVersion[]>(`${base(botId)}/versions?limit=20`),
  });
}

export function useModelOptions() {
  return useQuery({ queryKey: ["model-options"], queryFn: () => api<ModelOption[]>("/api/v1/model-options") });
}

function useInvalidate(botId: string) {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: ["config", botId] });
}

export function useSaveDraft(botId: string) {
  const invalidate = useInvalidate(botId);
  return useMutation({
    mutationFn: (config: BotConfig) =>
      api<BotConfigVersion>(`${base(botId)}/versions`, { method: "POST", body: JSON.stringify(config) }),
    onSuccess: invalidate,
  });
}

export function usePublish(botId: string) {
  const invalidate = useInvalidate(botId);
  return useMutation({
    mutationFn: (version: number) =>
      api<BotConfigVersion>(`${base(botId)}/versions/${version}/publish`, { method: "POST" }),
    onSuccess: invalidate,
  });
}

export function useRollback(botId: string) {
  const invalidate = useInvalidate(botId);
  return useMutation({
    mutationFn: (version: number) =>
      api<BotConfigVersion>(`${base(botId)}/versions/${version}/rollback`, { method: "POST" }),
    onSuccess: invalidate,
  });
}
