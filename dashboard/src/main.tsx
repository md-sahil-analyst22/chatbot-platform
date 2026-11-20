// ────────────────────────────────────────────────────────────────────────────────────────────
// 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
// What: The very first file the browser runs for Bot Studio (the dashboard).
// Does: Finds the empty <div id="root"> in index.html and draws the React app inside it.
// ────────────────────────────────────────────────────────────────────────────────────────────
// From react — React, the library that draws the user interface: StrictMode = extra checks
//   while developing.
import { StrictMode } from "react";
// From react-dom/client — React's browser renderer: createRoot = starts React in the page.
import { createRoot } from "react-dom/client";
// From ./app/App — the app skeleton: App = the whole app.
import { App } from "./app/App";
// Loads ./styles/global.css — the app-wide styles.
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
