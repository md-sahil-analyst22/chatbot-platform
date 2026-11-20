// ────────────────────────────────────────────────────────────────────────────────────────────
// 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
// What: The home page: lists your bots and has a small form to create a new one.
// ────────────────────────────────────────────────────────────────────────────────────────────
// From react — React, the library that draws the user interface: useState = remembers a value
//   between redraws; FormEvent = type of a form-submit event.
import { useState, type FormEvent } from "react";
// From react-router-dom — page navigation by URL: Link = a link to another page; useNavigate =
//   moves to another page from code.
import { Link, useNavigate } from "react-router-dom";
// From ../../components/Field — the shared form-field component: Field = label + input + error.
import { Field } from "../../components/Field";
// From ../../lib/api/types — the API data types: Language = en/hi/bn type.
import type { Language } from "../../lib/api/types";
// From ./api — this feature's API hooks: useBots = load the bots; useCreateBot = create a bot.
import { useBots, useCreateBot } from "./api";

// The languages a bot can speak.
const LANGUAGES: { value: Language; label: string }[] = [
  // English,
  { value: "en", label: "English" },
  // Hindi,
  { value: "hi", label: "Hindi" },
  // Bengali.
  { value: "bn", label: "Bengali" },
];

// The page component.
export function BotsPage() {
  // The bots list from the API (with loading/error state).
  const bots = useBots();
  // The 'create a bot' action.
  const createBot = useCreateBot();
  // A function to move to another page.
  const navigate = useNavigate();
  // The name typed in the form (starts empty).
  const [name, setName] = useState("");
  // The ticked languages (English by default).
  const [languages, setLanguages] = useState<Language[]>(["en"]);

  // Tick/untick a language.
  function toggle(lang: Language) {
    // Update the ticked languages:
    setLanguages((current) =>
      // if it's ticked, untick it; otherwise add it.
      current.includes(lang) ? current.filter((l) => l !== lang) : [...current, lang],
    );
  }

  // Create the bot, then open its Bot Studio editor.
  async function onSubmit(event: FormEvent) {
    // Stop the browser from reloading the page (the default for forms).
    event.preventDefault();
    // Create the bot (name without extra spaces) and wait for the answer.
    const bot = await createBot.mutateAsync({ name: name.trim(), languages });
    // Open the new bot's Bot Studio editor.
    navigate(`/bots/${bot.id}/config`);
  }

  // Return the page:
  return (
    // The page section.
    <section>
      {/* The heading. */}
      <h1>Your bots</h1>
      {/* While loading, say so. */}
      {bots.isLoading && <p>Loading...</p>}
      {/* If loading failed, show the error. */}
      {bots.error && <p className="error">Could not load bots: {bots.error.message}</p>}
      {/* The list of bots: */}
      <ul className="card-list">
        {/* one card per bot: */}
        {bots.data?.map((bot) => (
          // each card (`key` helps React track list items),
          <li key={bot.id} className="card">
            {/* the bot's name, */}
            <strong>{bot.name}</strong>
            {/* its languages, e.g. 'en · bn', */}
            <span className="muted">{bot.languages.join(" · ")}</span>
            {/* and a link to configure it. */}
            <Link to={`/bots/${bot.id}/config`}>Configure</Link>
          </li>
        ))}
      </ul>

      {/* The 'create a bot' form; submitting runs onSubmit. */}
      <form className="panel" onSubmit={onSubmit}>
        {/* Its heading. */}
        <h2>Create a bot</h2>
        {/* The name field with a hint: */}
        <Field label="Bot name" hint="Shown to your team, e.g. 'Website assistant'">
          {/* a text box tied to `name`, max 100 characters, required. */}
          <input value={name} onChange={(e) => setName(e.target.value)} maxLength={100} required />
        </Field>
        {/* The language checkboxes: */}
        <fieldset className="field">
          {/* their caption, */}
          <legend className="field-label">Languages</legend>
          {/* one checkbox per language: */}
          {LANGUAGES.map((l) => (
            // a label around each,
            <label key={l.value} className="inline">
              {/* the checkbox: */}
              <input
                // a checkbox,
                type="checkbox"
                // ticked if the language is chosen,
                checked={languages.includes(l.value)}
                // clicking it toggles the language.
                onChange={() => toggle(l.value)}
              />
              {/* The language name. */}
              {l.label}
            </label>
          ))}
        </fieldset>
        {/* The submit button, disabled until there's a name and a language (and while saving): */}
        <button type="submit" disabled={!name.trim() || languages.length === 0 || createBot.isPending}>
          {/* its text. */}
          Create bot
        </button>
        {/* If creating failed, show the error. */}
        {createBot.error && <p className="error">{createBot.error.message}</p>}
      </form>
    </section>
  );
}
