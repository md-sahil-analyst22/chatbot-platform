// ────────────────────────────────────────────────────────────────────────────────────────────
// 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
// What: The list of saved versions with their status, and a button to roll back to any of them.
// ────────────────────────────────────────────────────────────────────────────────────────────
// From ./api — this feature's API hooks: useRollback = roll back to a version; useVersions =
//   load versions.
import { useRollback, useVersions } from "./api";

// Shows the versions of one bot.
export function VersionHistory({ botId }: { botId: string }) {
  const versions = useVersions(botId);
  const rollback = useRollback(botId);

  return (
    <section className="panel">
      <h2>Version history</h2>
      {versions.data?.length === 0 && <p className="muted">No versions yet.</p>}
      <ul className="versions">
        {versions.data?.map((v) => (
          <li key={v.version}>
            <span>
              v{v.version} <span className={`status status-${v.status}`}>{v.status}</span>
            </span>
            <span className="muted">{new Date(v.created_at).toLocaleString()}</span>
            {v.status === "archived" && (
              <button type="button" className="link" onClick={() => rollback.mutate(v.version)}>
                Restore
              </button>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
