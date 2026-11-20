// ────────────────────────────────────────────────────────────────────────────────────────────
// 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
// What: The very first file the browser runs for Bot Studio (the dashboard).
// Does: Finds the empty <div id="root"> in index.html and draws the React app inside it.
// ────────────────────────────────────────────────────────────────────────────────────────────
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./app/App";
import "./styles/global.css";

// The spot in index.html where the app is drawn.
const root = document.getElementById("root");
if (!root) throw new Error("#root element missing");

// Start React. StrictMode adds extra checks while developing.
createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
