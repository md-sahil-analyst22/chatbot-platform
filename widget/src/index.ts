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
  if (!botKey) {
    console.warn("[saathi] data-bot-key missing; widget not mounted");
    return;
  }
  const button = document.createElement("button");
  button.type = "button";
  button.textContent = "Chat with us";
  button.setAttribute("aria-label", "Open chat");
  button.style.cssText =
    "position:fixed;right:20px;bottom:20px;padding:12px 16px;border-radius:999px;border:0;" +
    "background:#0F766E;color:#fff;font:600 14px system-ui;cursor:pointer;z-index:2147483000";
  document.body.appendChild(button);
}

// Wait until the page has loaded before adding the button.
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", mount);
} else {
  mount();
}
