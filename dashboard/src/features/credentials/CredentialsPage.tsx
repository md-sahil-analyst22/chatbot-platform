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
  return (
    <section>
      <h1>
        API keys <span className="badge">Pro</span>
      </h1>
      <p className="muted">
        By default your bots use Saathi&apos;s managed AI keys, with usage included in your plan.
        On the Pro plan you can connect your own provider account instead. Coming in Phase 8.
      </p>
      <div className="panel">
        <label className="field">
          <span className="field-label">Anthropic API key</span>
          <input type="password" autoComplete="off" placeholder="sk-ant-..." disabled />
          <span className="field-hint">Stored encrypted. Only the last 4 characters are ever shown.</span>
        </label>
        <button type="button" disabled>
          Save key (owners only)
        </button>
      </div>
    </section>
  );
}
