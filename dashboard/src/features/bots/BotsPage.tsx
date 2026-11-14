import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Field } from "../../components/Field";
import type { Language } from "../../lib/api/types";
import { useBots, useCreateBot } from "./api";

const LANGUAGES: { value: Language; label: string }[] = [
  { value: "en", label: "English" },
  { value: "hi", label: "Hindi" },
  { value: "bn", label: "Bengali" },
];

export function BotsPage() {
  const bots = useBots();
  const createBot = useCreateBot();
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [languages, setLanguages] = useState<Language[]>(["en"]);

  function toggle(lang: Language) {
    setLanguages((current) =>
      current.includes(lang) ? current.filter((l) => l !== lang) : [...current, lang],
    );
  }

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
