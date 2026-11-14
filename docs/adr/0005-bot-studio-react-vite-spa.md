# ADR-0005: Bot Studio as a React + Vite single-page app (instead of Next.js)

- **Status:** Proposed
- **Date:** 2026-11-12
- **Deciders:** Sahil

## Context
`02_ARCHITECTURE_AND_STACK.md` planned a Next.js admin dashboard. The dashboard is now the
self-serve **Bot Studio**: forms, validation, live preview, draft/publish, all behind a login.

## Problem
Choose a frontend that is quick to build and cheap to host for an authenticated admin app.

## Decision
React 19 + Vite + TypeScript, built to static files. React Query for API state, React Hook Form +
Zod for forms (schemas mirror backend limits), React Router for navigation. shadcn/ui may be added
later for components. Plain HTML/CSS/JS was rejected: forms, auth and state get unmanageable.

## Alternatives
- Next.js: server rendering and SEO are not needed behind a login; adds a Node server to run.
- Plain HTML + JS: fastest to start, slowest to maintain.

## Advantages
Static hosting (any CDN), fast dev server, no server to secure, same React skills as Next.js.

## Disadvantages
No server-side rendering (not needed); routing and data fetching chosen by us.

## Security impact
No server component to attack; tokens kept in memory by the auth SDK; tenant text rendered as
text only; Content-Security-Policy set by the static host.

## Performance impact
Initial bundle ~140 KB gzipped; acceptable for an admin app. Code-split routes if it grows.

## Operational impact
Deploy `dashboard/dist` to static hosting; CI runs typecheck, tests, build and `npm audit`.

## Consequences
Marketing pages, if ever needed, are a separate site.

## Revisit when
Public, SEO-relevant pages must be served from the same app.
