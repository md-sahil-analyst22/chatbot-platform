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
  const {
    register,
    formState: { errors },
  } = useFormContext<BotConfigForm>();
  const e = errors.branding;

  return (
    <section className="panel">
      <h2>Branding</h2>
      <Field label="Logo" hint="PNG, JPEG or WebP, up to 512 KB. Upload arrives in P4.13.">
        <input type="file" accept="image/png,image/jpeg,image/webp" disabled />
      </Field>
      <Field label="Header title" error={e?.header_title?.message}>
        <input maxLength={60} {...register("branding.header_title")} />
      </Field>
      <Field label="Header subtitle" error={e?.header_subtitle?.message}>
        <input maxLength={80} {...register("branding.header_subtitle")} />
      </Field>
      <Field label="Greeting message" error={e?.greeting?.message}>
        <textarea rows={2} maxLength={300} {...register("branding.greeting")} />
      </Field>
      <Field label="Footer text" error={e?.footer_text?.message}>
        <input maxLength={120} {...register("branding.footer_text")} />
      </Field>
      <div className="row">
        <Field label="Primary colour" error={e?.primary_color?.message}>
          <input type="color" {...register("branding.primary_color")} />
        </Field>
        <Field label="Launcher position">
          <select {...register("branding.launcher_position")}>
            <option value="right">Bottom right</option>
            <option value="left">Bottom left</option>
          </select>
        </Field>
      </div>
    </section>
  );
}
