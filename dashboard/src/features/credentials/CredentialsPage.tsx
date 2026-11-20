// ────────────────────────────────────────────────────────────────────────────────────────────
// 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
// What: Page for tenants' own API keys.
// Status: 🟡 Placeholder - built in Phase 8.
// ────────────────────────────────────────────────────────────────────────────────────────────
/**
 * Own provider API keys (BYOK) - Pro tier, Phase 8.1.
 * Contract: PUT /api/v1/credentials/{provider} {api_key} (OWNER) -> {provider, masked, status}.
 * The key is write-only: sent once, never displayed again, only "••••abcd" is shown.
 */
export function CredentialsPage() {
  // Return the page:
  return (
    // The page section.
    <section>
      {/* The heading: */}
      <h1>
        {/* 'API keys' with a Pro badge. */}
        API keys <span className="badge">Pro</span>
      </h1>
      {/* An explanation: */}
      <p className="muted">
        {/* (the text) */}
        By default your bots use Saathi&apos;s managed AI keys, with usage included in your plan.
        On the Pro plan you can connect your own provider account instead. Coming in Phase 8.
      </p>
      {/* A preview of the future form: */}
      <div className="panel">
        {/* the key field: */}
        <label className="field">
          {/* its label, */}
          <span className="field-label">Anthropic API key</span>
          {/* a hidden-text box, no autofill, switched off, */}
          <input type="password" autoComplete="off" placeholder="sk-ant-..." disabled />
          {/* and a reassuring note. */}
          <span className="field-hint">Stored encrypted. Only the last 4 characters are ever shown.</span>
        </label>
        {/* The save button, switched off: */}
        <button type="button" disabled>
          {/* its text. */}
          Save key (owners only)
        </button>
      </div>
    </section>
  );
}
