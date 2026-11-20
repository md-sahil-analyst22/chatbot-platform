// ────────────────────────────────────────────────────────────────────────────────────────────
// 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
// What: Test chat against your draft before publishing.
// Status: 🟡 Placeholder - works once chat exists (Phase 3).
// ────────────────────────────────────────────────────────────────────────────────────────────
// From react — React, the library that draws the user interface: useState = remembers a value
//   between redraws.
import { useState } from "react";
// From react-router-dom — page navigation by URL: useParams = reads values from the URL (e.g.
//   botId).
import { useParams } from "react-router-dom";

/**
 * Test chat against the latest DRAFT config before publishing.
 * Wired in P3.8: POST /api/v1/bots/{botId}/playground {version, message} -> SSE stream.
 */
export function PlaygroundPage() {
  const { botId } = useParams();
  const [message, setMessage] = useState("");

  return (
    <section>
      <h1>Playground</h1>
      <p className="muted">
        Try your draft before customers see it. Bot <code>{botId}</code>. Available once the chat
        endpoint ships (Phase 3).
      </p>
      <div className="panel">
        <textarea
          rows={3}
          placeholder="e.g. GST filing er fees koto?"
          value={message}
          onChange={(e) => setMessage(e.target.value)}
        />
        <button type="button" disabled>
          Send (Phase 3)
        </button>
      </div>
    </section>
  );
}
