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
  // Retry a failed request once; treat loaded data as fresh for 30 seconds.
  defaultOptions: { queries: { retry: 1, staleTime: 30_000 } },
});

// Every page is shown inside the shared Layout (sidebar + content).
export function App() {
  // Return the page structure (JSX: HTML-like code that React turns into the page):
  return (
    // Every page can use the data cache.
    <QueryClientProvider client={queryClient}>
      {/* Turn on navigation by URL. */}
      <BrowserRouter>
        {/* The list of URL -> page rules: */}
        <Routes>
          {/* All pages below are shown inside the shared Layout (sidebar + content). */}
          <Route element={<Layout />}>
            {/* / -> the bots list. */}
            <Route index element={<BotsPage />} />
            {/* /bots/<id>/config -> the Bot Studio editor. */}
            <Route path="bots/:botId/config" element={<ConfigEditorPage />} />
            {/* /bots/<id>/playground -> the test chat. */}
            <Route path="bots/:botId/playground" element={<PlaygroundPage />} />
            {/* /settings/api-keys -> the API keys page. */}
            <Route path="settings/api-keys" element={<CredentialsPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
