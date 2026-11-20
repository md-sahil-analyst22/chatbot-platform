// ────────────────────────────────────────────────────────────────────────────────────────────
// 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
// What: A live preview of the chat widget that updates as you type in the branding fields.
// ────────────────────────────────────────────────────────────────────────────────────────────
// From react-hook-form — form state and validation: useFormContext = uses the form created by a
//   parent component.
import { useFormContext } from "react-hook-form";
// From ../bot-config/schema — the Bot Studio form rules: BotConfigForm = type of the form data.
import type { BotConfigForm } from "../bot-config/schema";

/** Live preview of the website widget. All tenant text is rendered as plain text. */
// Reads the branding values from the shared form.
export function WidgetPreview() {
  // Take `watch` from the shared form (it re-draws when values change).
  const { watch } = useFormContext<BotConfigForm>();
  // The current branding values, live.
  const b = watch("branding");

  // Return the preview:
  return (
    // The panel box.
    <section className="panel">
      {/* The heading. */}
      <h2>Preview</h2>
      {/* The fake widget; its accent colour comes from the chosen colour. */}
      <div className="widget-preview" style={{ ["--accent" as string]: b.primary_color }}>
        {/* Its header: */}
        <header className="wp-header">
          {/* a round 'logo' (hidden from screen readers): */}
          <div className="wp-logo" aria-hidden>
            {/* the title's first letter, or 'S'. */}
            {b.header_title.trim().charAt(0).toUpperCase() || "S"}
          </div>
          {/* The title block: */}
          <div>
            {/* the title (or a default), */}
            <div className="wp-title">{b.header_title || "Chat with us"}</div>
            {/* the subtitle, only if set. */}
            {b.header_subtitle && <div className="wp-subtitle">{b.header_subtitle}</div>}
          </div>
        </header>
        {/* The chat area: */}
        <div className="wp-body">
          {/* the greeting bubble, only if set. */}
          {b.greeting && <div className="wp-bubble">{b.greeting}</div>}
        </div>
        {/* The footer, only if set. */}
        {b.footer_text && <footer className="wp-footer">{b.footer_text}</footer>}
      </div>
      {/* Which side the launcher sits on. */}
      <p className="muted">Launcher: bottom {b.launcher_position}</p>
    </section>
  );
}
