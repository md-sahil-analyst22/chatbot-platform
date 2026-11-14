/**
 * Saathi widget entry (placeholder - real UI in P4.2).
 * Reads the public bot key from its own <script> tag and mounts a launcher button.
 */
const script = document.currentScript as HTMLScriptElement | null;
const botKey = script?.dataset.botKey;

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

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", mount);
} else {
  mount();
}
