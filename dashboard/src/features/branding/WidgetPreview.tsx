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
  const { watch } = useFormContext<BotConfigForm>();
  const b = watch("branding");

  return (
    <section className="panel">
      <h2>Preview</h2>
      <div className="widget-preview" style={{ ["--accent" as string]: b.primary_color }}>
        <header className="wp-header">
          <div className="wp-logo" aria-hidden>
            {b.header_title.trim().charAt(0).toUpperCase() || "S"}
          </div>
          <div>
            <div className="wp-title">{b.header_title || "Chat with us"}</div>
            {b.header_subtitle && <div className="wp-subtitle">{b.header_subtitle}</div>}
          </div>
        </header>
        <div className="wp-body">
          {b.greeting && <div className="wp-bubble">{b.greeting}</div>}
        </div>
        {b.footer_text && <footer className="wp-footer">{b.footer_text}</footer>}
      </div>
      <p className="muted">Launcher: bottom {b.launcher_position}</p>
    </section>
  );
}
