import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { Layout } from "../components/Layout";
import { BotsPage } from "../features/bots/BotsPage";
import { ConfigEditorPage } from "../features/bot-config/ConfigEditorPage";
import { CredentialsPage } from "../features/credentials/CredentialsPage";
import { PlaygroundPage } from "../features/playground/PlaygroundPage";

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, staleTime: 30_000 } },
});

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
