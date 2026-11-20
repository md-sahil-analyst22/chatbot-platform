// Dependency audit for CI (REPO_STRUCTURE 2.2): fails on any HIGH or CRITICAL npm advisory,
// except reviewed, unexpired entries in audit-exceptions.json. No dependencies: Node + npm only.
//
// Why not plain `npm audit --audit-level=high`? It has no way to tolerate one advisory that has no
// fix yet without also ignoring every future one. This keeps the check strict for everything else.
// From node:child_process — Node.js: run another program: spawnSync = runs a program and waits.
import { spawnSync } from "node:child_process";
// From node:fs — Node.js: read files: readFileSync = reads a file.
import { readFileSync } from "node:fs";

// Only these severities fail the check.
const BLOCKING = new Set(["high", "critical"]);
// Today's date as YYYY-MM-DD (to compare with expiry dates).
const today = new Date().toISOString().slice(0, 10);

// Run `npm audit --json` and wait for it (allowing a large output).
const run = spawnSync("npm", ["audit", "--json"], { encoding: "utf8", maxBuffer: 64 * 1024 * 1024 });
// The parsed audit report.
let report;
// Try to read the report as JSON:
try {
  // (parse it)
  report = JSON.parse(run.stdout);
// Not JSON (e.g. no network):
} catch {
  // explain,
  console.error("audit-check: npm audit produced no JSON (network or registry error) - failing closed.");
  // show npm's own error output,
  console.error(run.stderr);
  // and fail (fail closed: no report means no pass).
  process.exit(1);
}
// npm reported an error inside the JSON:
if (report.error) {
  // explain,
  console.error(`audit-check: npm audit error - failing closed: ${JSON.stringify(report.error)}`);
  // and fail.
  process.exit(1);
}

// Read the reviewed exceptions from audit-exceptions.json:
const { exceptions } = JSON.parse(
  // the file next to this folder, as text.
  readFileSync(new URL("../audit-exceptions.json", import.meta.url), "utf8"),
);
// Exceptions by advisory id.
const byId = new Map(exceptions.map((e) => [e.id, e]));

// Collect each advisory once (packages that only depend on a vulnerable one list names, not advisories).
const advisories = new Map();
// Go through every vulnerable package in the report:
for (const vuln of Object.values(report.vulnerabilities ?? {})) {
  // and each reason it's listed:
  for (const via of vuln.via) {
    // a real advisory (not just a package name) that is high or critical...
    if (typeof via === "object" && BLOCKING.has(via.severity)) {
      // ...take its id from the end of its URL,
      const id = String(via.url).split("/").pop();
      // and store it once, with the package, severity, title and link.
      advisories.set(id, { id, pkg: via.name, severity: via.severity, title: via.title, url: via.url });
    }
  }
}

// The problems that will fail the check.
const failures = [];
// For every blocking advisory:
for (const adv of advisories.values()) {
  // find its exception, if any;
  const exc = byId.get(adv.id);
  // no exception:
  if (!exc) {
    // it's a failure;
    failures.push(`${adv.severity.toUpperCase()} ${adv.pkg}: ${adv.title} (${adv.url})`);
  // an exception missing a reason or a valid expiry date:
  } else if (!/^\d{4}-\d{2}-\d{2}$/.test(exc.expires ?? "") || !exc.reason) {
    // also a failure;
    failures.push(`exception ${adv.id} needs a "reason" and an "expires" date (YYYY-MM-DD)`);
  // an exception that has expired:
  } else if (exc.expires < today) {
    // also a failure, with a hint:
    failures.push(
      `exception ${adv.id} (${adv.pkg}) EXPIRED on ${exc.expires}: re-check for a fix, then update or remove it`,
    );
  // a valid exception:
  } else {
    // log that it's tolerated until its expiry date.
    console.log(`tolerated until ${exc.expires}: ${adv.severity} ${adv.pkg} ${adv.id} (reviewed exception)`);
  }
}
// For every exception:
for (const exc of exceptions) {
  // if it no longer matches any advisory...
  if (!advisories.has(exc.id)) {
    // ...print a note suggesting to remove it:
    console.log(
      `note: exception ${exc.id} (${exc.package}) no longer matches any advisory - remove it from audit-exceptions.json`,
    );
  }
}

// Any failures:
if (failures.length) {
  // print how many,
  console.error(`\naudit-check FAILED (${failures.length}):`);
  // list them,
  for (const f of failures) console.error(`  - ${f}`);
  // and fail.
  process.exit(1);
}
// Otherwise: passed.
console.log(`audit-check passed: no unreviewed high/critical advisories (${advisories.size} seen).`);
