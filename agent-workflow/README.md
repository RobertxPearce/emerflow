# agent-workflow

Shows **how the Hospital Swarm agents make a decision, step by step, while it happens.**
It draws a flowchart of the agents. Each box lights up as that agent works, and clicking a box
shows what it received, what it decided and why. It also shows a decision log and bed counts.

Everything for this part lives in this one directory: the UI package, the simulation, the demo
and its npm/Python setup. Nothing outside it is needed. Other parts use it by importing a React
component and giving it data. Right now the data comes from a SimPy hospital simulation. That
source can be replaced with anything that produces the same events (see
[Plugging in other data](#plugging-in-other-data)).

```
agent-workflow/
├── ui/       React package "@hospital-swarm/agent-workflow": the part other pages import
├── server/   Python: SimPy hospital simulation + server that streams events
└── demo/     Next.js app with three example pages that use the package
```

---

## Quick start

Run every command from this directory (`agent-workflow/`):

```bash
cd agent-workflow
npm install                 # installs ui + demo (npm workspaces)
npm run setup               # first time only: Python venv + SimPy/FastAPI
npm run server              # terminal 1: simulation on http://localhost:8000
npm run demo                # terminal 2: demo on http://localhost:3000
```

| Demo page | Shows |
| --- | --- |
| `/` | The full panel. Switch **Data source** to "Recorded run" to run with no Python server |
| `/embed` | A mock partner dashboard with its own button, using only some of the pieces |
| `/adapter` | Different data and a different graph, driven by the same components |

**No Python?** Skip the server. The UI includes a recorded run (`replaySource()`), and the
`/` page can switch to it.

---

## How it works

```
 data source ──events──▶ useSwarmRun() ──state──▶ components
 (server / replay /       (ui/src/use-swarm-run.ts)  (WorkflowCanvas, StepDetails,
  pushed by your code)                                DecisionLog, HospitalSnapshot)
```

1. A **data source** (`ui/src/sources.ts`) starts a run and emits **events**.
2. **`useSwarmRun()`** turns those events into state: which step is running or done, what each
   step decided, bed counts, and the log.
3. **Components** draw that state. They never fetch data themselves, so they don't care where it
   came from.
4. The **graph** (steps and arrows) is part of the data. The source sends a `workflow` event and
   the canvas lays it out automatically, so a different pipeline needs no UI code changes.

### The simulation (server/)

`server/workflow.py` runs one crisis against a SimPy model (`server/hospital.py`) and yields events:

| Step | Kind | What it does |
| --- | --- | --- |
| Mass Casualty Event | event | 15–60 casualties (severity 1–5) arrive over 20 minutes |
| Hospital Engine | code | Simulates the day 08:00 → 21:47: admissions, discharges, busy nurses |
| ER / ICU / Staffing Agent | AI\* | Each reads only its own unit's simulated state and says what it needs |
| Coordinator | AI\* | Decides whether stable ICU patients should move to step-down to make room |
| Bed Calculator | code | Places patients by severity without going over capacity. **No AI.** |
| DeepChart Check | AI\* | Checks each transfer's medication records; flags real disagreements |
| Charge Nurse Review | human | Flagged transfers pause for a person |
| Simulated Outcome | code | Re-runs the same hospital (same seed) with and without the plan, then compares waits |

\*Rule-based stand-ins for now, so it runs without an API key. Each is one function in
`server/workflow.py` that returns a `step_done(...)` event. To use Gemini, replace the function
body and return the same event.

---

## What it needs and expects

### To use the UI in another app

- Install it from the partner app's directory with a path to this package, for example
  `npm install ../agent-workflow/ui`. This adds `"@hospital-swarm/agent-workflow": "file:../agent-workflow/ui"`
  to its `package.json`, so it always uses the latest code in this directory.
- React 18+ (developed on React 19 / Next.js 16).
- Styling uses **one** of:
  - **Tailwind v4 in the app:** add `@source "<path-to>/agent-workflow/ui/src";` to its CSS.
  - **No Tailwind:** `import "@hospital-swarm/agent-workflow/styles.css";`. This has only the
    classes the components use and no global reset, so it won't restyle the rest of the page.
- The package ships TypeScript source. Next.js: add
  `transpilePackages: ["@hospital-swarm/agent-workflow"]` to `next.config`. Vite handles workspace
  TS on its own.
- Components are client components (`"use client"`).
- Each component fills the width it's given. Give `WorkflowCanvas` a height through `className`.

### To run the simulation server

- Python 3.10+ with `server/requirements.txt` (simpy, fastapi, uvicorn).
- `GET /run?casualties=25&seed=1234&pace=1.0` streams events as Server-Sent Events.
  `seed` replays the same crisis exactly; `pace` scales the pauses between steps (0 = no pauses).
- CORS: only `http://localhost:3000` is allowed by default. Allow other pages with
  `ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5173 npm run server`.

### The event protocol (the contract)

Every data source must emit these, in this order: `meta → workflow → (step | snapshot)* → end`.
TypeScript: `ui/src/protocol.ts`. Python builders: `server/protocol.py`.

```jsonc
{ "type": "meta", "protocol": 1, "seed": 4821 }                // anything extra is kept in swarm.meta
{ "type": "workflow",                                           // graph to draw (optional; else the default)
  "steps": [{ "id": "icu", "kind": "ai", "title": "ICU Agent", "role": "Speaks for intensive care only." }],
  "edges": [{ "source": "engine", "target": "icu" }] }
{ "type": "step", "id": "icu", "status": "running" }
{ "type": "step", "id": "icu", "status": "done",               // or "flagged" = a person must check
  "summary": "1 bed left, critical only.",                      // one line, shown on the box and in the log
  "input": ["ICU: 47 / 48"], "output": ["Offer: 1 bed"],        // "Received" / "Decided" lists
  "reasoning": "I keep the last beds for the sickest patients." } // "Why" (may be null)
{ "type": "snapshot", "label": "At crisis (21:47)", "clock": "21:47",
  "units": [{ "code": "ICU", "name": "Intensive Care", "occupied": 47, "capacity": 48, "waiting": 0 }] }
{ "type": "error", "message": "…" }                              // stops the run and shows the message
{ "type": "end" }
```

Rules: step ids are unique; a step sends `running` before `done`/`flagged`; several steps may be
`running` at once (parallel); `kind` is `trigger | code | ai | human`, and any other string
also works with a neutral badge.

---

## Using it in a partner's page

**Everything, one line:**

```tsx
import { SwarmPanel } from "@hospital-swarm/agent-workflow";

<SwarmPanel />                                   // live server at http://localhost:8000
<SwarmPanel source={replaySource()} />           // recorded run, no server
```

**Your own button and layout:**

```tsx
"use client";
import { useSwarmRun, sseSource, WorkflowCanvas, StepDetails } from "@hospital-swarm/agent-workflow";

const source = sseSource({ url: "http://localhost:8000/run" });

export function CrisisView() {
  const swarm = useSwarmRun({
    source,
    onEvent: (e) => { /* update other parts of your page */ },
    onComplete: (run) => console.log(run.results.outcome?.summary),
  });
  return (
    <>
      <button onClick={() => swarm.start({ casualties: 25 })}>Trigger Mass Casualty Event</button>
      <WorkflowCanvas swarm={swarm} layout="vertical" className="h-[560px]" />
      <StepDetails swarm={swarm} />
    </>
  );
}
```

Full example: `demo/src/app/embed/page.tsx`.

### API

**`useSwarmRun({ source?, workflow?, onEvent?, onComplete? })`** returns `swarm`:

| Field | |
| --- | --- |
| `phase` | `"idle" \| "running" \| "complete" \| "error"` |
| `start(params?)` | Start a run. `params` go to the source (the SSE source adds them to the URL) |
| `reset()` / `select(id)` | Clear everything / choose the step `StepDetails` shows |
| `workflow` | The graph being drawn (the default, or the source's `workflow` event) |
| `statuses[id]`, `results[id]` | Each step's status and `{ summary, input, output, reasoning }` |
| `snapshots`, `log`, `meta`, `error`, `selectedId` | Bed counts, decision log, meta event, error text, selected step |

**Components** all take `swarm`, plus an optional `className`:

| Component | Extra props |
| --- | --- |
| `SwarmPanel` | Everything. `source`, `workflow`, `onEvent`, `onComplete`, `swarm` (use your own), `showControls`, `casualtyOptions`, `errorHint`, `title` |
| `WorkflowCanvas` | `layout="horizontal" \| "vertical"` |
| `StepDetails`, `DecisionLog`, `HospitalSnapshot` | — |
| `SwarmControls` | `casualtyOptions` (`[]` hides the picker), `defaultCasualties` |
| `SwarmError` | `hint` |

---

## Plugging in other data

Pick whichever fits the data you have:

| Your data | Use |
| --- | --- |
| A server that can send the protocol over SSE | `sseSource({ url })` |
| A server that sends SSE in another shape | `sseSource({ url, map: (raw) => SwarmEvent \| SwarmEvent[] \| null })` |
| Data already in the page (API response, websocket, state) | `pushSource()`, then call `push(event)` for each event |
| A saved run (demo, offline, tests) | `replaySource(recordedRun, { speed })` |
| Something else (WebSocket, polling, n8n…) | Write a `SwarmSource`, shown below |

```ts
const mySource: SwarmSource = {
  start(params, emit) {
    const ws = new WebSocket("wss://…");
    ws.onmessage = (m) => emit(toSwarmEvent(JSON.parse(m.data)));  // your adapter
    return () => ws.close();                                       // called on reset/unmount
  },
};
```

`demo/src/app/adapter/page.tsx` is a complete example: a made-up partner format, a different
4-step graph, and one `toSwarmEvent()` adapter function.

**Changing the simulation's steps:** edit `STEPS`/`EDGES` and `run()` in `server/workflow.py`,
then run `npm run record` to refresh the recorded run. The UI's default graph is read
from that recording, so both stay in sync. No positions are needed.

---

## Checking changes

```bash
npm run check              # protocol check over 300 simulated runs + typecheck + lint + build
```

`server/check.py` fails with the seed of any run that breaks the protocol, so it can be replayed
(`GET /run?seed=…`).

## Files

| File | Purpose |
| --- | --- |
| `ui/src/index.ts` | Public API: everything partners may import |
| `ui/src/protocol.ts` | Event types (the contract) |
| `ui/src/sources.ts` | `sseSource`, `replaySource`, `pushSource` |
| `ui/src/use-swarm-run.ts` | Event → state |
| `ui/src/workflow.ts` | Default graph, automatic layout, recorded run |
| `ui/src/components/` | The visual pieces |
| `ui/src/fixtures/sample-run.json` | Recorded run (generated by `server/record_fixture.py`) |
| `ui/styles.css` | Prebuilt CSS for apps without Tailwind (`npm run css`) |
| `server/protocol.py` | Python event builders (mirror of `protocol.ts`) |
| `server/workflow.py` | The decision pipeline and its agents |
| `server/hospital.py` | SimPy hospital model |
| `server/server.py` | FastAPI SSE endpoint |
| `server/check.py`, `server/record_fixture.py` | Protocol check / recording |

## Known limits

- The agents are rules, not a model yet (see above).
- The simulation is a simplified model built for a demo, not validated against real hospital data.
  Across 300 random runs, the plan shortened waits for severity 1–2 patients in about 65%, never
  lengthened them, and made no difference in the rest. Less severe patients sometimes wait
  longer, and the Outcome step says so when it happens.
- All patients and records are generated. No real patient data is used.
