// ────────────────────────────────────────────────────────────────────────────────────────────
// 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
// What: The app's skeleton: data-fetching setup and the list of pages (routes).
// Pages: / = bots list · /bots/:id/config = Bot Studio editor · /bots/:id/playground = test
//        chat · /settings/api-keys = own API keys.
// ────────────────────────────────────────────────────────────────────────────────────────────
// From @tanstack/react-query — React Query, loads and caches data from the API: QueryClient =
//   the data cache; QueryClientProvider = gives every page access to the cache.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
// From react-router-dom — page navigation by URL: BrowserRouter = turns on URL-based
//   navigation; Route = one URL -> page rule; Routes = the list of rules.
import { BrowserRouter, Route, Routes } from "react-router-dom";
// From ../components/Layout — the page frame: Layout = the frame component.
import { Layout } from "../components/Layout";
// From ../features/bots/BotsPage — the bots list page: BotsPage = the page component.
import { BotsPage } from "../features/bots/BotsPage";
// From ../features/bot-config/ConfigEditorPage — the Bot Studio editor: ConfigEditorPage = the
//   page component.
import { ConfigEditorPage } from "../features/bot-config/ConfigEditorPage";
// From ../features/credentials/CredentialsPage — the API-keys page: CredentialsPage = the page
//   component.
import { CredentialsPage } from "../features/credentials/CredentialsPage";
// From ../features/playground/PlaygroundPage — the test-chat page: PlaygroundPage = the page
//   component.
import { PlaygroundPage } from "../features/playground/PlaygroundPage";

// React Query caches server data for 30 s and retries a failed request once.
const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, staleTime: 30_000 } },
});

// Every page is shown inside the shared Layout (sidebar + content).
export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<BotsPage />} />
            <Route path="bots/:botId/config" element={<ConfigEditorPage />} />
            <Route path="bots/:botId/playground" element={<PlaygroundPage />} />
            <Route path="settings/api-keys" element={<CredentialsPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
