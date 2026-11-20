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
  // The bot id from the address bar.
  const { botId } = useParams();
  // The message typed in the box.
  const [message, setMessage] = useState("");

  // Return the page:
  return (
    // The page section.
    <section>
      {/* The heading. */}
      <h1>Playground</h1>
      {/* An explanation: */}
      <p className="muted">
        {/* (the text, showing the bot id) */}
        Try your draft before customers see it. Bot <code>{botId}</code>. Available once the chat
        endpoint ships (Phase 3).
      </p>
      {/* The future chat box: */}
      <div className="panel">
        {/* a text area: */}
        <textarea
          // 3 lines tall,
          rows={3}
          // with an example Banglish question,
          placeholder="e.g. GST filing er fees koto?"
          // showing the typed text,
          value={message}
          // and remembering what's typed.
          onChange={(e) => setMessage(e.target.value)}
        />
        {/* The send button, switched off until Phase 3: */}
        <button type="button" disabled>
          {/* its text. */}
          Send (Phase 3)
        </button>
      </div>
    </section>
  );
}
