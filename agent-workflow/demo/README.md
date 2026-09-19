# agent-workflow demo

Next.js app showing `@hospital-swarm/agent-workflow` in use:

- `src/app/page.tsx`: full panel, with the data source switchable between live server and recorded run
- `src/app/embed/page.tsx`: a partner-style dashboard with its own trigger, using only some pieces
- `src/app/adapter/page.tsx`: a different data format and graph, through `pushSource()` and an adapter function

Run it from `agent-workflow/` with `npm run demo`. See [`../README.md`](../README.md).
