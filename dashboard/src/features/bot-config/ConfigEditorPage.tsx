// ────────────────────────────────────────────────────────────────────────────────────────────
// 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
// What: The Bot Studio editor: instructions, model, answer style, branding, live preview, save
//       and publish.
// How: One form (react-hook-form) shared by all sections; the rules come from schema.ts.
// ────────────────────────────────────────────────────────────────────────────────────────────
import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect, useState } from "react";
import { FormProvider, useForm } from "react-hook-form";
import { Link, useParams } from "react-router-dom";
import { Field } from "../../components/Field";
import { BrandingEditor } from "../branding/BrandingEditor";
import { WidgetPreview } from "../branding/WidgetPreview";
import { useDraft, useModelOptions, usePublish, useSaveDraft } from "./api";
import { STYLE_PRESETS } from "./presets";
import { DEFAULT_CONFIG, botConfigSchema, type BotConfigForm } from "./schema";
import { VersionHistory } from "./VersionHistory";

// The page component; botId comes from the address bar.
export function ConfigEditorPage() {
  const { botId = "" } = useParams();
  const draft = useDraft(botId);
  const models = useModelOptions();
  const saveDraft = useSaveDraft(botId);
  const publish = usePublish(botId);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [bannedText, setBannedText] = useState("");

  // Create the form with the browser-side rules and default values.
  const form = useForm<BotConfigForm>({
    resolver: zodResolver(botConfigSchema),
    defaultValues: DEFAULT_CONFIG,
  });
  const { register, handleSubmit, reset, watch, setValue, formState } = form;

  // When the saved draft arrives, fill the form with it.
  useEffect(() => {
    if (draft.data) {
      reset(draft.data.config);
      setBannedText(draft.data.config.prompt.banned_topics.join(", "));
    }
  }, [draft.data, reset]);

  // Watch the advanced temperature field to show its current value.
  const override = watch("generation.temperature_override");

  // Check the form, then save it as a new draft.
  const onSave = handleSubmit(async (values) => {
    await saveDraft.mutateAsync(values);
  });

  // The version number the Publish button will make live.
  const latestDraftVersion = saveDraft.data?.version ?? draft.data?.version;

  return (
    <FormProvider {...form}>
      <div className="page-header">
        <h1>Configure bot</h1>
        <Link to={`/bots/${botId}/playground`}>Open playground</Link>
      </div>

      <div className="editor">
        <form className="editor-form" onSubmit={onSave}>
          <section className="panel">
            <h2>Personality</h2>
            <Field label="Persona and tone" hint="e.g. Polite receptionist for a family clinic. Short, warm answers.">
              <textarea rows={3} {...register("prompt.persona")} />
            </Field>
            <Field label="Brand rules" hint="Words to use or avoid, how to refer to your business.">
              <textarea rows={3} {...register("prompt.brand_rules")} />
            </Field>
            <Field label="Topics the bot must never discuss" hint="Comma-separated">
              <input
                value={bannedText}
                onChange={(e) => {
                  setBannedText(e.target.value);
                  setValue(
                    "prompt.banned_topics",
                    e.target.value.split(",").map((t) => t.trim()).filter(Boolean),
                  );
                }}
              />
            </Field>
          </section>

          <section className="panel">
            <h2>Response style</h2>
            {STYLE_PRESETS.map((preset) => (
              <label key={preset.value} className="radio-card">
                <input type="radio" value={preset.value} {...register("generation.style")} />
                <span>
                  <strong>{preset.label}</strong>
                  <span className="muted">{preset.help}</span>
                </span>
              </label>
            ))}
          </section>

          <section className="panel">
            <button type="button" className="link" onClick={() => setShowAdvanced((v) => !v)}>
              {showAdvanced ? "Hide" : "Show"} advanced settings (admins)
            </button>
            {showAdvanced && (
              <>
                <Field label="Model" hint="Only models available on your plan are listed.">
                  <select {...register("generation.model_key")}>
                    {models.data?.map((m) => (
                      <option key={m.key} value={m.key}>
                        {m.label}
                      </option>
                    ))}
                  </select>
                </Field>
                <label className="inline">
                  <input
                    type="checkbox"
                    checked={override !== null}
                    onChange={(e) => setValue("generation.temperature_override", e.target.checked ? 0.3 : null)}
                  />
                  Set temperature manually (overrides response style)
                </label>
                {override !== null && (
                  <Field label={`Temperature: ${override.toFixed(2)}`} hint="0 = most predictable, 1 = most creative">
                    <input
                      type="range"
                      min={0}
                      max={1}
                      step={0.05}
                      {...register("generation.temperature_override", { valueAsNumber: true })}
                    />
                  </Field>
                )}
                <Field label="Maximum answer length (tokens)">
                  <input type="number" min={64} max={2000} {...register("generation.max_output_tokens", { valueAsNumber: true })} />
                </Field>
                <Field
                  label="Additional instructions"
                  hint="Added below the platform's safety rules. They cannot override grounding or safety."
                  error={formState.errors.prompt?.custom_instructions?.message}
                >
                  <textarea rows={5} {...register("prompt.custom_instructions")} />
                </Field>
              </>
            )}
          </section>

          <BrandingEditor />

          <div className="actions">
            <button type="submit" disabled={saveDraft.isPending}>
              Save draft
            </button>
            <button
              type="button"
              className="primary"
              disabled={!latestDraftVersion || publish.isPending}
              onClick={() => latestDraftVersion && publish.mutate(latestDraftVersion)}
            >
              Publish{latestDraftVersion ? ` v${latestDraftVersion}` : ""}
            </button>
          </div>
          {saveDraft.error && <p className="error">{saveDraft.error.message}</p>}
          {publish.isSuccess && <p className="success">Published. Your widget picks it up within a minute.</p>}
        </form>

        <aside className="editor-side">
          <WidgetPreview />
          <VersionHistory botId={botId} />
        </aside>
      </div>
    </FormProvider>
  );
}
