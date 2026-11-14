import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../../lib/api/client";
import type { Bot, BotCreate } from "../../lib/api/types";

export function useBots() {
  return useQuery({ queryKey: ["bots"], queryFn: () => api<Bot[]>("/api/v1/bots") });
}

export function useCreateBot() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: BotCreate) =>
      api<Bot>("/api/v1/bots", { method: "POST", body: JSON.stringify(body) }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["bots"] }),
  });
}
