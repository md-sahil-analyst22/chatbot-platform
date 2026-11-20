// ────────────────────────────────────────────────────────────────────────────────────────────
// 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
// What: The chat widget that tenants paste onto their own website with a <script> tag.
// Status: 🟡 Today it only shows a 'Chat with us' button; the real chat window comes in Phase 4.
// Security: 🔒 It only knows the bot's PUBLIC key (data-bot-key); no secrets ever go into this
//           file.
// ────────────────────────────────────────────────────────────────────────────────────────────
/**
 * Saathi widget entry (placeholder - real UI in P4.2).
 * Reads the public bot key from its own <script> tag and mounts a launcher button.
 */
// The <script> tag that loaded this file.
const script = document.currentScript as HTMLScriptElement | null;
// The public bot key from data-bot-key="...".
const botKey = script?.dataset.botKey;

// Add the launcher button to the page.
function mount(): void {
  // No key on the script tag:
  if (!botKey) {
    // warn in the browser console...
    console.warn("[saathi] data-bot-key missing; widget not mounted");
    // ...and stop.
    return;
  }
  // Create a <button> element.
  const button = document.createElement("button");
  // A plain button (not a form submit).
  button.type = "button";
  // Its label.
  button.textContent = "Chat with us";
  // A description for screen readers.
  button.setAttribute("aria-label", "Open chat");
  // Its look, set inline so the host website's styles don't matter:
  button.style.cssText =
    // fixed in the bottom-right corner, rounded, no border,
    "position:fixed;right:20px;bottom:20px;padding:12px 16px;border-radius:999px;border:0;" +
    // teal background, white text, and on top of everything else on the page.
    "background:#0F766E;color:#fff;font:600 14px system-ui;cursor:pointer;z-index:2147483000";
  // Add it to the page.
  document.body.appendChild(button);
}

// Wait until the page has loaded before adding the button.
if (document.readyState === "loading") {
  // The page is still loading: add the button once it's ready.
  document.addEventListener("DOMContentLoaded", mount);
// Otherwise...
} else {
  // ...add it right away.
  mount();
}
