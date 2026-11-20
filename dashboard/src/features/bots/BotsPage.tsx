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
  { value: "en", label: "English" },
  { value: "hi", label: "Hindi" },
  { value: "bn", label: "Bengali" },
];

// The page component.
export function BotsPage() {
  const bots = useBots();
  const createBot = useCreateBot();
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [languages, setLanguages] = useState<Language[]>(["en"]);

  // Tick/untick a language.
  function toggle(lang: Language) {
    setLanguages((current) =>
      current.includes(lang) ? current.filter((l) => l !== lang) : [...current, lang],
    );
  }

  // Create the bot, then open its Bot Studio editor.
  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    const bot = await createBot.mutateAsync({ name: name.trim(), languages });
    navigate(`/bots/${bot.id}/config`);
  }

  return (
    <section>
      <h1>Your bots</h1>
      {bots.isLoading && <p>Loading...</p>}
      {bots.error && <p className="error">Could not load bots: {bots.error.message}</p>}
      <ul className="card-list">
        {bots.data?.map((bot) => (
          <li key={bot.id} className="card">
            <strong>{bot.name}</strong>
            <span className="muted">{bot.languages.join(" · ")}</span>
            <Link to={`/bots/${bot.id}/config`}>Configure</Link>
          </li>
        ))}
      </ul>

      <form className="panel" onSubmit={onSubmit}>
        <h2>Create a bot</h2>
        <Field label="Bot name" hint="Shown to your team, e.g. 'Website assistant'">
          <input value={name} onChange={(e) => setName(e.target.value)} maxLength={100} required />
        </Field>
        <fieldset className="field">
          <legend className="field-label">Languages</legend>
          {LANGUAGES.map((l) => (
            <label key={l.value} className="inline">
              <input
                type="checkbox"
                checked={languages.includes(l.value)}
                onChange={() => toggle(l.value)}
              />
              {l.label}
            </label>
          ))}
        </fieldset>
        <button type="submit" disabled={!name.trim() || languages.length === 0 || createBot.isPending}>
          Create bot
        </button>
        {createBot.error && <p className="error">{createBot.error.message}</p>}
      </form>
    </section>
  );
}
