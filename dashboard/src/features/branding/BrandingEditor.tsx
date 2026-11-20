// ────────────────────────────────────────────────────────────────────────────────────────────
// 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
// What: The branding section of Bot Studio: title, subtitle, greeting, colour, position,
//       footer.
// ────────────────────────────────────────────────────────────────────────────────────────────
// From react-hook-form — form state and validation: useFormContext = uses the form created by a
//   parent component.
import { useFormContext } from "react-hook-form";
// From ../../components/Field — the shared form-field component: Field = label + input + error.
import { Field } from "../../components/Field";
// From ../bot-config/schema — the Bot Studio form rules: BotConfigForm = type of the form data.
import type { BotConfigForm } from "../bot-config/schema";

// Uses the shared Bot Studio form (useFormContext).
export function BrandingEditor() {
  // Take from the shared Bot Studio form:
  const {
    // the function that ties an input to a form field,
    register,
    // and the validation errors.
    formState: { errors },
  } = useFormContext<BotConfigForm>();
  // Short name for the branding errors.
  const e = errors.branding;

  // Return the section:
  return (
    // The panel box.
    <section className="panel">
      {/* The heading. */}
      <h2>Branding</h2>
      {/* Logo field (switched off until uploads exist): */}
      <Field label="Logo" hint="PNG, JPEG or WebP, up to 512 KB. Upload arrives in P4.13.">
        {/* a file picker limited to PNG/JPEG/WebP, disabled. */}
        <input type="file" accept="image/png,image/jpeg,image/webp" disabled />
      </Field>
      {/* Title field, showing its error if any: */}
      <Field label="Header title" error={e?.header_title?.message}>
        {/* a text box tied to branding.header_title, max 60 characters. */}
        <input maxLength={60} {...register("branding.header_title")} />
      </Field>
      {/* Subtitle field: */}
      <Field label="Header subtitle" error={e?.header_subtitle?.message}>
        {/* a text box tied to branding.header_subtitle, max 80. */}
        <input maxLength={80} {...register("branding.header_subtitle")} />
      </Field>
      {/* Greeting field: */}
      <Field label="Greeting message" error={e?.greeting?.message}>
        {/* a 2-line text area tied to branding.greeting, max 300. */}
        <textarea rows={2} maxLength={300} {...register("branding.greeting")} />
      </Field>
      {/* Footer field: */}
      <Field label="Footer text" error={e?.footer_text?.message}>
        {/* a text box tied to branding.footer_text, max 120. */}
        <input maxLength={120} {...register("branding.footer_text")} />
      </Field>
      {/* A row with two fields side by side: */}
      <div className="row">
        {/* Colour field: */}
        <Field label="Primary colour" error={e?.primary_color?.message}>
          {/* the browser's colour picker, tied to branding.primary_color. */}
          <input type="color" {...register("branding.primary_color")} />
        </Field>
        {/* Launcher position field: */}
        <Field label="Launcher position">
          {/* a drop-down tied to branding.launcher_position: */}
          <select {...register("branding.launcher_position")}>
            {/* bottom right, */}
            <option value="right">Bottom right</option>
            {/* bottom left. */}
            <option value="left">Bottom left</option>
          </select>
        </Field>
      </div>
    </section>
  );
}
