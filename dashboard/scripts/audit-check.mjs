// Dependency audit for CI (REPO_STRUCTURE 2.2): fails on any HIGH or CRITICAL npm advisory,
// except reviewed, unexpired entries in audit-exceptions.json. No dependencies: Node + npm only.
//
// Why not plain `npm audit --audit-level=high`? It has no way to tolerate one advisory that has no
// fix yet without also ignoring every future one. This keeps the check strict for everything else.
import { spawnSync } from "node:child_process";
import { readFileSync } from "node:fs";

const BLOCKING = new Set(["high", "critical"]);
const today = new Date().toISOString().slice(0, 10);

const run = spawnSync("npm", ["audit", "--json"], { encoding: "utf8", maxBuffer: 64 * 1024 * 1024 });
let report;
try {
  report = JSON.parse(run.stdout);
} catch {
  console.error("audit-check: npm audit produced no JSON (network or registry error) - failing closed.");
  console.error(run.stderr);
  process.exit(1);
}
if (report.error) {
  console.error(`audit-check: npm audit error - failing closed: ${JSON.stringify(report.error)}`);
  process.exit(1);
}

const { exceptions } = JSON.parse(
  readFileSync(new URL("../audit-exceptions.json", import.meta.url), "utf8"),
);
const byId = new Map(exceptions.map((e) => [e.id, e]));

// Collect each advisory once (packages that only depend on a vulnerable one list names, not advisories).
const advisories = new Map();
for (const vuln of Object.values(report.vulnerabilities ?? {})) {
  for (const via of vuln.via) {
    if (typeof via === "object" && BLOCKING.has(via.severity)) {
      const id = String(via.url).split("/").pop();
      advisories.set(id, { id, pkg: via.name, severity: via.severity, title: via.title, url: via.url });
    }
  }
}

const failures = [];
for (const adv of advisories.values()) {
  const exc = byId.get(adv.id);
  if (!exc) {
    failures.push(`${adv.severity.toUpperCase()} ${adv.pkg}: ${adv.title} (${adv.url})`);
  } else if (!/^\d{4}-\d{2}-\d{2}$/.test(exc.expires ?? "") || !exc.reason) {
    failures.push(`exception ${adv.id} needs a "reason" and an "expires" date (YYYY-MM-DD)`);
  } else if (exc.expires < today) {
    failures.push(
      `exception ${adv.id} (${adv.pkg}) EXPIRED on ${exc.expires}: re-check for a fix, then update or remove it`,
    );
  } else {
    console.log(`tolerated until ${exc.expires}: ${adv.severity} ${adv.pkg} ${adv.id} (reviewed exception)`);
  }
}
for (const exc of exceptions) {
  if (!advisories.has(exc.id)) {
    console.log(
      `note: exception ${exc.id} (${exc.package}) no longer matches any advisory - remove it from audit-exceptions.json`,
    );
  }
}

if (failures.length) {
  console.error(`\naudit-check FAILED (${failures.length}):`);
  for (const f of failures) console.error(`  - ${f}`);
  process.exit(1);
}
console.log(`audit-check passed: no unreviewed high/critical advisories (${advisories.size} seen).`);
