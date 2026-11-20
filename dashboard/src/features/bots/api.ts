// ────────────────────────────────────────────────────────────────────────────────────────────
// 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
// What: Hooks that load and create bots (via React Query, which caches and refreshes the data).
// ────────────────────────────────────────────────────────────────────────────────────────────
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../../lib/api/client";
import type { Bot, BotCreate } from "../../lib/api/types";

// Load the bots list.
export function useBots() {
  return useQuery({ queryKey: ["bots"], queryFn: () => api<Bot[]>("/api/v1/bots") });
}

// Create a bot, then refresh the list.
export function useCreateBot() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: BotCreate) =>
      api<Bot>("/api/v1/bots", { method: "POST", body: JSON.stringify(body) }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["bots"] }),
  });
}
