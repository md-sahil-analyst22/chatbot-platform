// ────────────────────────────────────────────────────────────────────────────────────────────
// 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
// What: The list of saved versions with their status, and a button to roll back to any of them.
// ────────────────────────────────────────────────────────────────────────────────────────────
// From ./api — this feature's API hooks: useRollback = roll back to a version; useVersions =
//   load versions.
import { useRollback, useVersions } from "./api";

// Shows the versions of one bot.
export function VersionHistory({ botId }: { botId: string }) {
  // The version list from the API.
  const versions = useVersions(botId);
  // The 'roll back' action.
  const rollback = useRollback(botId);

  // Return the panel:
  return (
    // The panel box.
    <section className="panel">
      {/* The heading. */}
      <h2>Version history</h2>
      {/* No versions yet -> say so. */}
      {versions.data?.length === 0 && <p className="muted">No versions yet.</p>}
      {/* The list: */}
      <ul className="versions">
        {/* one row per version: */}
        {versions.data?.map((v) => (
          // each row,
          <li key={v.version}>
            {/* the version number and its status badge: */}
            <span>
              {/* e.g. 'v3 published'. */}
              v{v.version} <span className={`status status-${v.status}`}>{v.status}</span>
            </span>
            {/* When it was saved, in the viewer's local time. */}
            <span className="muted">{new Date(v.created_at).toLocaleString()}</span>
            {/* Old (archived) versions get a Restore button: */}
            {v.status === "archived" && (
              // clicking it rolls back to this version,
              <button type="button" className="link" onClick={() => rollback.mutate(v.version)}>
                {/* its text. */}
                Restore
              </button>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
