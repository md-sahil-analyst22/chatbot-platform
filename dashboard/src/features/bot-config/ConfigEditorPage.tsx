// ────────────────────────────────────────────────────────────────────────────────────────────
// 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
// What: The Bot Studio editor: instructions, model, answer style, branding, live preview, save
//       and publish.
// How: One form (react-hook-form) shared by all sections; the rules come from schema.ts.
// ────────────────────────────────────────────────────────────────────────────────────────────
// From @hookform/resolvers/zod — connects zod rules to react-hook-form: zodResolver = checks
//   the form with zod rules.
import { zodResolver } from "@hookform/resolvers/zod";
// From react — React, the library that draws the user interface: useEffect = runs code after
//   the page draws; useState = remembers a value between redraws.
import { useEffect, useState } from "react";
// From react-hook-form — form state and validation: FormProvider = shares a form with child
//   components; useForm = creates a form.
import { FormProvider, useForm } from "react-hook-form";
// From react-router-dom — page navigation by URL: Link = a link to another page; useParams =
//   reads values from the URL (e.g. botId).
import { Link, useParams } from "react-router-dom";
// From ../../components/Field — the shared form-field component: Field = label + input + error.
import { Field } from "../../components/Field";
// From ../branding/BrandingEditor — the branding section: BrandingEditor = the branding
//   component.
import { BrandingEditor } from "../branding/BrandingEditor";
// From ../branding/WidgetPreview — the live widget preview: WidgetPreview = the preview
//   component.
import { WidgetPreview } from "../branding/WidgetPreview";
// From ./api — this feature's API hooks: useDraft = load the draft; useModelOptions = load
//   allowed models; usePublish = publish a version; useSaveDraft = save a draft.
import { useDraft, useModelOptions, usePublish, useSaveDraft } from "./api";
// From ./presets — the answer-style choices: STYLE_PRESETS = the style choices.
import { STYLE_PRESETS } from "./presets";
// From ./schema — the Bot Studio form rules: DEFAULT_CONFIG = starting values; botConfigSchema
//   = the form rules; BotConfigForm = type of the form data.
import { DEFAULT_CONFIG, botConfigSchema, type BotConfigForm } from "./schema";
// From ./VersionHistory — the version list: VersionHistory = the version list component.
import { VersionHistory } from "./VersionHistory";

// The page component; botId comes from the address bar.
export function ConfigEditorPage() {
  // The bot id from the address bar (empty text if missing).
  const { botId = "" } = useParams();
  // The saved draft (loading/error/data).
  const draft = useDraft(botId);
  // The models the plan allows.
  const models = useModelOptions();
  // The 'save draft' action.
  const saveDraft = useSaveDraft(botId);
  // The 'publish' action.
  const publish = usePublish(botId);
  // Whether the advanced section is open (closed at first).
  const [showAdvanced, setShowAdvanced] = useState(false);
  // The banned topics as typed, e.g. 'medical, legal'.
  const [bannedText, setBannedText] = useState("");

  // Create the form with the browser-side rules and default values.
  const form = useForm<BotConfigForm>({
    // check values with the zod rules from schema.ts,
    resolver: zodResolver(botConfigSchema),
    // start from the default values.
    defaultValues: DEFAULT_CONFIG,
  });
  // Pull out the form tools we use below.
  const { register, handleSubmit, reset, watch, setValue, formState } = form;

  // When the saved draft arrives, fill the form with it.
  useEffect(() => {
    // Once the draft has loaded...
    if (draft.data) {
      // ...put its values into the form,
      reset(draft.data.config);
      // and show its banned topics as comma-separated text.
      setBannedText(draft.data.config.prompt.banned_topics.join(", "));
    }
  // Run again only when the draft or `reset` changes.
  }, [draft.data, reset]);

  // Watch the advanced temperature field to show its current value.
  const override = watch("generation.temperature_override");

  // Check the form, then save it as a new draft.
  const onSave = handleSubmit(async (values) => {
    // Save the checked values as a new draft and wait for the answer.
    await saveDraft.mutateAsync(values);
  });

  // The version number the Publish button will make live.
  const latestDraftVersion = saveDraft.data?.version ?? draft.data?.version;

  // Return the page:
  return (
    // Share the form with child components (BrandingEditor, WidgetPreview).
    <FormProvider {...form}>
      {/* The page header: */}
      <div className="page-header">
        {/* the heading, */}
        <h1>Configure bot</h1>
        {/* a link to the test chat. */}
        <Link to={`/bots/${botId}/playground`}>Open playground</Link>
      </div>

      {/* Two columns: the form and the side panel. */}
      <div className="editor">
        {/* The form; submitting saves a draft. */}
        <form className="editor-form" onSubmit={onSave}>
          {/* Section: personality. */}
          <section className="panel">
            {/* Its heading. */}
            <h2>Personality</h2>
            {/* Persona field with a hint: */}
            <Field label="Persona and tone" hint="e.g. Polite receptionist for a family clinic. Short, warm answers.">
              {/* a 3-line text area tied to prompt.persona. */}
              <textarea rows={3} {...register("prompt.persona")} />
            </Field>
            {/* Brand rules field: */}
            <Field label="Brand rules" hint="Words to use or avoid, how to refer to your business.">
              {/* a text area tied to prompt.brand_rules. */}
              <textarea rows={3} {...register("prompt.brand_rules")} />
            </Field>
            {/* Banned topics field: */}
            <Field label="Topics the bot must never discuss" hint="Comma-separated">
              {/* a text box: */}
              <input
                // showing the typed text,
                value={bannedText}
                // and when it changes:
                onChange={(e) => {
                  // remember the typed text,
                  setBannedText(e.target.value);
                  // and set prompt.banned_topics to:
                  setValue(
                    // (that form field)
                    "prompt.banned_topics",
                    // the text split at commas, trimmed, empty ones dropped.
                    e.target.value.split(",").map((t) => t.trim()).filter(Boolean),
                  );
                }}
              />
            </Field>
          </section>

          {/* Section: response style. */}
          <section className="panel">
            {/* Its heading. */}
            <h2>Response style</h2>
            {/* One radio card per style preset: */}
            {STYLE_PRESETS.map((preset) => (
              // a clickable card,
              <label key={preset.value} className="radio-card">
                {/* the radio button tied to generation.style, */}
                <input type="radio" value={preset.value} {...register("generation.style")} />
                {/* and its text: */}
                <span>
                  {/* the name, */}
                  <strong>{preset.label}</strong>
                  {/* the help text. */}
                  <span className="muted">{preset.help}</span>
                </span>
              </label>
            ))}
          </section>

          {/* Section: advanced settings. */}
          <section className="panel">
            {/* A button that opens/closes it: */}
            <button type="button" className="link" onClick={() => setShowAdvanced((v) => !v)}>
              {/* 'Show' or 'Hide', depending on the state. */}
              {showAdvanced ? "Hide" : "Show"} advanced settings (admins)
            </button>
            {/* Only when open: */}
            {showAdvanced && (
              // a fragment (groups elements without adding a box):
              <>
                {/* Model choice: */}
                <Field label="Model" hint="Only models available on your plan are listed.">
                  {/* a drop-down tied to generation.model_key, */}
                  <select {...register("generation.model_key")}>
                    {/* one option per allowed model: */}
                    {models.data?.map((m) => (
                      // each option,
                      <option key={m.key} value={m.key}>
                        {/* showing its label. */}
                        {m.label}
                      </option>
                    ))}
                  </select>
                </Field>
                {/* The 'set temperature manually' checkbox: */}
                <label className="inline">
                  {/* the checkbox: */}
                  <input
                    // a checkbox,
                    type="checkbox"
                    // ticked when a manual temperature is set,
                    checked={override !== null}
                    // ticking sets 0.3, unticking clears it (back to the style's value).
                    onChange={(e) => setValue("generation.temperature_override", e.target.checked ? 0.3 : null)}
                  />
                  {/* Its text. */}
                  Set temperature manually (overrides response style)
                </label>
                {/* Only when a manual temperature is set: */}
                {override !== null && (
                  // a field whose label shows the current value,
                  <Field label={`Temperature: ${override.toFixed(2)}`} hint="0 = most predictable, 1 = most creative">
                    {/* a slider: */}
                    <input
                      // a range slider,
                      type="range"
                      // from 0,
                      min={0}
                      // to 1,
                      max={1}
                      // in steps of 0.05,
                      step={0.05}
                      // tied to generation.temperature_override, as a number.
                      {...register("generation.temperature_override", { valueAsNumber: true })}
                    />
                  </Field>
                )}
                {/* Reply length field: */}
                <Field label="Maximum answer length (tokens)">
                  {/* a number box from 64 to 2000, tied to generation.max_output_tokens. */}
                  <input type="number" min={64} max={2000} {...register("generation.max_output_tokens", { valueAsNumber: true })} />
                </Field>
                {/* Additional instructions field: */}
                <Field
                  // its label,
                  label="Additional instructions"
                  // its hint,
                  hint="Added below the platform's safety rules. They cannot override grounding or safety."
                  // and the validation error for that field, if any.
                  error={formState.errors.prompt?.custom_instructions?.message}
                >
                  {/* A 5-line text area tied to prompt.custom_instructions. */}
                  <textarea rows={5} {...register("prompt.custom_instructions")} />
                </Field>
              </>
            )}
          </section>

          {/* The branding section (features/branding/BrandingEditor.tsx). */}
          <BrandingEditor />

          {/* The buttons: */}
          <div className="actions">
            {/* Save draft (disabled while saving): */}
            <button type="submit" disabled={saveDraft.isPending}>
              {/* its text; */}
              Save draft
            </button>
            {/* Publish: */}
            <button
              // a plain button (not a form submit),
              type="button"
              // styled as the main action,
              className="primary"
              // disabled until there's a draft (and while publishing),
              disabled={!latestDraftVersion || publish.isPending}
              // clicking publishes the latest draft.
              onClick={() => latestDraftVersion && publish.mutate(latestDraftVersion)}
            >
              {/* 'Publish v3' style text. */}
              Publish{latestDraftVersion ? ` v${latestDraftVersion}` : ""}
            </button>
          </div>
          {/* If saving failed, show the error. */}
          {saveDraft.error && <p className="error">{saveDraft.error.message}</p>}
          {/* After publishing, confirm it. */}
          {publish.isSuccess && <p className="success">Published. Your widget picks it up within a minute.</p>}
        </form>

        {/* The side panel: */}
        <aside className="editor-side">
          {/* the live widget preview, */}
          <WidgetPreview />
          {/* the version history. */}
          <VersionHistory botId={botId} />
        </aside>
      </div>
    </FormProvider>
  );
}
