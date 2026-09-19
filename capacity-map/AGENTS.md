# Notes for AI coding agents

Read `README.md` in this directory first. This file lists the rules that are easy to break.

## Boundaries

- Partners import only what `ui/src/index.ts` exports. Treat everything else as internal.
- Components never fetch. All data enters through a `RegionSource` (`ui/src/sources.ts`) and the
  hooks (`use-region.ts`, `use-simulation.ts`). New data = new source, not component changes.
  The one exception is `use-weather-alerts.ts`, which calls the public NWS API directly.
- Statuses, ER waits and the casualty distribution (`status()`, `er_wait_minutes()`,
  `distribute()` in `../agent-workflow/server/region.py`) must stay deterministic code. Do not
  move them into an LLM call. Every color on the map has to be explainable.
- Never present simulated capacity as real. Keep the "simulated" note in the footer and the
  "Recorded snapshot" label.
- Leaflet must only load in the browser. Import it only in `components/leaflet-map.tsx`, which
  `components/capacity-map.tsx` lazy-loads after mount.

## Data shapes are a contract

- Defined twice: `ui/src/types.ts` and `../agent-workflow/server/region.py`. Change both together.
- After changing `region.py`, run `npm run record` so the offline fixtures match.

## Styling

- Tailwind v4 utility classes only in components. Leaflet's DOM is styled in `ui/src/map.css`,
  page motion in `ui/src/effects.css` (prefix classes with `emf-`). Keep every animation inside
  `@media (prefers-reduced-motion: no-preference)`, and use `animation-fill-mode: backwards`
  (not `both`) so hover transforms still work after an entrance animation.
- Red, amber and green mean hospital status. Use the indigo/sky brand colors for everything else.
- After changing classes in `ui/src`, run `npm run css` to rebuild `ui/styles.css`.

## Verify before finishing

All npm commands run from `capacity-map/`, which is its own npm workspace root. The Python checks
use the agent-workflow venv (`cd ../agent-workflow && npm run setup` once).

```bash
npm run check   # region rules over 60 incidents + typecheck + lint + demo build
```

Then check the demo (`npm run server` + `npm run demo`): `/` (run a simulation), `/embed`, and `/`
with the server stopped (recorded data).

## Gotchas

- `demo/` is Next.js 16. Read `demo/AGENTS.md` before changing Next-specific code.
- `npm run lint` only lints `demo/`. The package source isn't covered by it.
- `useSimulation` ignores results from earlier runs using a run id. Keep that guard if you refactor.
- `FlyToSelected` in `leaflet-map.tsx` depends on primitives on purpose: hospital objects are new
  on every refresh and every simulation frame.
- The recorded source's `simulate()` returns its own scenario wherever the incident was placed;
  `useSimulation` moves the incident marker to the recorded location.
