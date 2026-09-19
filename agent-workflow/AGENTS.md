# Notes for AI coding agents

Read `README.md` in this directory first. This file lists the rules that are easy to break.

## Boundaries

- Partners import only what `ui/src/index.ts` exports. Treat everything else as internal.
- Components never fetch data. All data enters through a `SwarmSource` (`ui/src/sources.ts`) and
  `useSwarmRun` (`ui/src/use-swarm-run.ts`). Keep it that way. New data = new source or `map`
  function, not component changes.
- The bed placement math (`bed_calculator` in `server/workflow.py`) must stay deterministic code.
  Do not move it into an LLM call.
- DeepChart and the UI must never state which conflicting record is correct. They only flag
  (`status: "flagged"`) and show both sides.

## The protocol is a contract

- Defined twice: `ui/src/protocol.ts` (types) and `server/protocol.py` (builders). Change both
  together, and bump `PROTOCOL_VERSION` in both if the change is not backwards compatible.
- Order: `meta → workflow → (step | snapshot)* → end` (or `error`). A step sends `running` before
  `done`/`flagged`. Step ids in `step` events must exist in the `workflow` event.
- The UI's default graph comes from `ui/src/fixtures/sample-run.json`. After changing steps or
  event contents in `server/workflow.py`, run `npm run record` (from `agent-workflow/`).

## Styling

- Tailwind v4 utility classes only, no CSS files per component. Container queries (`@container`,
  `@3xl:`) are used so components adapt to their slot, not the screen.
- After changing classes in `ui/src`, run `npm run css` to rebuild `ui/styles.css`
  (used by apps without Tailwind).

## Verify before finishing

All npm commands run from `agent-workflow/`, which is its own npm workspace root.

```bash
npm run check   # protocol check (300 runs) + typecheck + lint + demo build
```

Then check the demo pages (`npm run server` + `npm run demo`): `/`, `/embed`,
`/adapter`, and `/` with the data source set to "Recorded run".

## Gotchas

- `demo/` is Next.js 16. Read `demo/AGENTS.md` before changing Next-specific code.
- `sseSource` closes the stream on `end`/`error` on purpose. Otherwise `EventSource` reconnects
  and replays the run.
- `useSwarmRun` ignores events from earlier runs using a run id. Keep that guard if you refactor.
- Python agent functions return `(step_done(...), data_for_next_step)`. The UI only ever sees the
  first part.
