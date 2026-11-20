// ────────────────────────────────────────────────────────────────────────────────────────────
// 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
// What: Hooks that load and create bots (via React Query, which caches and refreshes the data).
// ────────────────────────────────────────────────────────────────────────────────────────────
// From @tanstack/react-query — React Query, loads and caches data from the API: useMutation =
//   sends a change to the API; useQuery = loads data from the API; useQueryClient = access to the
//   data cache.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
// From ../../lib/api/client — the API caller: api = calls the API.
import { api } from "../../lib/api/client";
// From ../../lib/api/types — the API data types: Bot = bot type; BotCreate = create-bot
//   request type.
import type { Bot, BotCreate } from "../../lib/api/types";

// Load the bots list.
export function useBots() {
  // Load GET /api/v1/bots, cached under the name 'bots'.
  return useQuery({ queryKey: ["bots"], queryFn: () => api<Bot[]>("/api/v1/bots") });
}

// Create a bot, then refresh the list.
export function useCreateBot() {
  // Access to the data cache.
  const queryClient = useQueryClient();
  // Return a 'mutation' (an action that changes data):
  return useMutation({
    // what it does: send the new bot...
    mutationFn: (body: BotCreate) =>
      // ...as POST /api/v1/bots with a JSON body;
      api<Bot>("/api/v1/bots", { method: "POST", body: JSON.stringify(body) }),
    // afterwards: mark the cached bots list stale so it reloads.
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["bots"] }),
  });
}
