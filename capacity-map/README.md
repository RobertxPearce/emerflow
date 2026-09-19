# capacity-map

The **public side of EmerFlow**: a page for civilians and EMS crews that shows how full every
nearby emergency department is, which hospital gets you care fastest, and local emergency news.
It also has a **what-if simulator**: drop a mass-casualty incident anywhere on the map and watch
the swarm spread casualties across hospitals, compared with sending everyone to the nearest
trauma center.

Everything for this part lives in this one directory: the UI package, the demo site and the
checks. Live data comes from the swarm server in [`../agent-workflow/server`](../agent-workflow/server);
without it, everything still runs on recorded data.

```
capacity-map/
├── ui/        React package "@hospital-swarm/capacity-map": the part other pages import
├── demo/      Next.js site: the public home page, staff login pages, a partner example
└── scripts/   check.py (rules over many simulated incidents), record.py (offline fixtures)
```

---

## Quick start

Run every command from this directory (`capacity-map/`):

```bash
cd capacity-map
npm install                 # installs ui + demo (npm workspaces)
npm run server              # terminal 1: swarm server on http://localhost:8000 (first time: see below)
npm run demo                # terminal 2: site on http://localhost:3001
```

The server is the agent-workflow one. The first time, set it up with
`cd ../agent-workflow && npm install && npm run setup`.

| Page | Shows |
| --- | --- |
| `/` | The public home page: map, closest hospitals, simulator, local emergency news |
| `/embed` | A mock EMS dispatch console using only some pieces, with its own layout |
| `/login/hospital`, `/login/doctor` | Staff sign-in pages (not connected to an identity provider yet) |

**No Python?** Skip the server. The page says "Recorded snapshot" and the simulator plays a
recorded scenario (60 casualties near the stadium downtown) wherever you click.

---

## What's on the page

- **Hero.** Live status, a rotating ticker of what's changing, and region stats that count up.
  Click a stat to filter the map (e.g. "At capacity" shows only full hospitals). **Run the crisis
  demo** places an 80-casualty incident at the stadium downtown and plays it: the fastest way to
  see the simulator.
- **Map.** Every hospital is a dot colored by ER status (green accepting, amber busy, red at
  capacity), sized by ER capacity. Hover for status and ER wait, click for ER/ICU beds and
  directions. Full hospitals pulse. Hovering a hospital in the list rings its dot and opens its
  label on the map, and the other way round. The legend is a filter: click a status to hide or show it. A dashed line runs from
  you to the hospital with the fastest care. Click the map once to enable scroll zoom.
- **Closest hospitals.** Sorted by distance, or by **Fastest** (estimated drive + ER wait). The
  fastest option is marked. **EMS crew** view adds ER/ICU bed bars and trauma levels.
- **Region stats.** Hospitals accepting, at capacity, open ER bays and median ER wait.
- **Simulate an incident.** Click the button, click the map, choose the size, run. Red lines
  show where the swarm sent casualties (hover for counts), dots change color as the timeline
  plays, and the side panel compares the outcome with sending everyone to the nearest trauma
  center: average time to a bed, longest wait, and casualties still without a bed after 3 hours.
- **Local emergency news.** Active incidents, full hospitals (each with the nearest open
  alternative), and National Weather Service alerts for your area.

## Where the data comes from

| Data | Source |
| --- | --- |
| Hospital capacity, incidents | Swarm server `GET /region`: one SimPy hospital per real Baltimore hospital (simulated load), from 08:00 to now. `agent-workflow/server/region.py` |
| What-if simulation | Swarm server `GET /simulate?lat&lon&casualties`: see below |
| Weather alerts | `api.weather.gov`, straight from the browser (US only, no key). The location is rounded to ~1 km |
| Map | Esri World Light Gray Canvas tiles |
| Your location | Browser geolocation, asked only when you press "Use my location" (or already allowed). More than 60 mi from the region, distances are measured from downtown |

**Status colors** are plain rules (`status()` in `region.py`): **red** if anyone is waiting for an
ER or ICU bed or the ER is ≥ 97% full, **amber** if the ER or ICU is ≥ 85% full, otherwise **green**.

### How the simulator decides (`region.py`)

1. Every hospital is simulated up to the moment of the incident, so the plan uses real (simulated)
   free beds, minus 10% kept back for the hospital's usual patients.
2. **`distribute()`** places casualties sickest first. Severity 1–2 go to trauma centers only. Each
   goes where drive time + 30 min for every patient beyond the hospital's free beds is lowest.
   Surgery patients also need an ICU bed afterwards. Plain code, no AI: the same incident always
   gives the same plan.
3. Every hospital is played forward 3 hours with its casualties arriving after the drive, and the
   same incident is played with **every casualty sent to the nearest trauma center**, which is
   what happens without coordination.

`npm run check` runs 60 random incidents at random times of day. Coordination got casualties to a
bed faster on average in 52, the same in 3, and up to 3 minutes slower in 5 (spreading patients
out adds driving). It never left more casualties without a bed.

---

## Using it in another app

- Install with a path: `npm install ../capacity-map/ui` → `"@hospital-swarm/capacity-map": "file:../capacity-map/ui"`.
- React 19. Components are client components.
- Styling uses **one** of:
  - **Tailwind v4 in the app:** add `@source "<path-to>/capacity-map/ui/src";` to its CSS.
  - **No Tailwind:** `import "@hospital-swarm/capacity-map/styles.css";` (only the classes the
    components use, no global reset).
  - Leaflet's CSS and the map's own CSS are imported by the map component automatically.
- Next.js: add `transpilePackages: ["@hospital-swarm/capacity-map"]` to `next.config`.
- The map loads Leaflet only in the browser, so server rendering is safe without `next/dynamic`.
- The swarm server only accepts pages from `http://localhost:3000` and `:3001`. Allow others with
  `ALLOWED_ORIGINS=http://localhost:5173 npm run server` (comma-separated).

**Everything, one line:**

```tsx
import { CapacityDashboard } from "@hospital-swarm/capacity-map";

<CapacityDashboard />                                   // swarm server, recorded data if it's down
<CapacityDashboard source={recordedSource()} />         // recorded data only
<CapacityDashboard showNews={false} showSimulator={false} />
```

**Your own layout** (full example: `demo/src/app/embed/page.tsx`):

```tsx
"use client";
import { CapacityMap, HospitalList, rankHospitals, swarmSource, useRegion } from "@hospital-swarm/capacity-map";

const source = swarmSource({ url: "http://localhost:8000" });

export function Destinations({ unit }: { unit: [number, number] }) {
  const { data } = useRegion(source);
  const ranked = data ? rankHospitals(data.hospitals, unit, "fastest") : [];
  return (
    <>
      <CapacityMap className="h-[480px]" hospitals={data?.hospitals ?? []} location={unit} route={ranked[0] ? { to: ranked[0] } : null} />
      <HospitalList hospitals={ranked} audience="ems" bestId={ranked[0]?.id} />
    </>
  );
}
```

### API

| Export | |
| --- | --- |
| `CapacityDashboard` | Everything. `source`, `title`, `subtitle`, `showNews`, `showSimulator` |
| `CapacityMap` | The map. `hospitals`, `incidents`, `location`, `selectedId`/`onSelect`, `hoveredId`/`onHover`, `visible` (status filter), `route`, `simulation`, `children` (overlays). Give it a height |
| `HospitalList` | Rows from `rankHospitals()`. `audience`, `selectedId`/`onSelect`, `hoveredId`/`onHover`, `bestId` |
| `StatusLegend` | Status counts that toggle a filter. `counts`, `visible`, `onToggle` |
| `RegionStats` | Headline numbers that count up. `tone`, `onPick` (makes tiles clickable) |
| `LiveTicker`, `NewsFeed` | One rotating line of live news; incidents + full hospitals + weather |
| `SimulationPanel`, `SimulationTimeline`, `SimulationVerdict` | Simulator setup, comparison, playback, and the end-of-playback result. Take the `useSimulation()` state |
| `useRegion(source, { refreshMs })` | `{ data, kind, error }`, refreshed every 30 s by default |
| `useSimulation(source)` | `phase`, `point`, `casualties`, `result`, `frame`, and `begin/place/run/start/play/pause/seek/exit` (`start(point, n)` places and runs in one step) |
| `useCountUp(n)` | Animates a number toward `n` |
| `useLocation()`, `useWeatherAlerts(location)` | Browser location; NWS alerts |
| `rankHospitals(hospitals, from, "nearest" \| "fastest")` | Adds `distance`, `drive`, `total` and sorts |

### Plugging in other data

Components never fetch. Data comes from a `RegionSource`:

| Your data | Use |
| --- | --- |
| The swarm server | `swarmSource({ url })` |
| Recorded fixtures (demo, offline, tests) | `recordedSource(region?, simulation?)` |
| Live with a fallback | `withFallback(primary, fallback = recordedSource())` (the default) |
| Anything else | Write a `RegionSource` |

```ts
const mySource: RegionSource = {
  kind: "live",
  region: () => fetch("/api/hospitals").then((r) => r.json()).then(toRegionSnapshot), // your adapter
  // simulate is optional; without it CapacityDashboard hides the simulator
};
```

The shapes are in `ui/src/types.ts` and mirror `region.py`.

---

## Checking changes

```bash
npm run check    # rules over 24 snapshots and 60 random incidents + typecheck + lint + demo build
npm run record   # after changing region.py: refresh the offline fixtures in ui/src/fixtures/
npm run css      # after changing classes in ui/src: rebuild ui/styles.css
```

`scripts/check.py` fails with the scenario that broke a rule, so it can be replayed with
`region.simulate(**scenario)`. It checks that no unit goes over capacity, statuses follow the
rules, every casualty is assigned, severe casualties only go to trauma centers, and coordination
is never meaningfully worse than nearest-only.

## Files

| File | Purpose |
| --- | --- |
| `ui/src/index.ts` | Public API: everything partners may import |
| `ui/src/types.ts` | Data shapes (mirror `region.py`) |
| `ui/src/sources.ts` | `swarmSource`, `recordedSource`, `withFallback` |
| `ui/src/use-*.ts` | Region polling, simulator state and playback, location, weather alerts |
| `ui/src/geo.ts` | Status colors, distance, drive time, ranking |
| `ui/src/components/` | The visual pieces. `leaflet-map.tsx` is the map itself, loaded by `capacity-map.tsx` |
| `ui/src/map.css` | Leaflet overrides, pulses, halos and casualty-flow animation |
| `ui/src/effects.css` | Page motion: entrances, heartbeat line, ticker, button shine (off with reduced motion) |
| `ui/src/fixtures/` | Recorded `/region` and `/simulate` responses (`npm run record`) |
| `demo/src/app/` | The site: home page, login pages, `/embed` partner example |
| `../agent-workflow/server/region.py` | Hospitals, statuses, casualty distribution, simulation |

## Known limits

- **All capacity numbers are simulated.** The hospitals and their locations are real; their load
  is not. The page says so in the footer.
- The simulated region is Baltimore only.
- Drive times are straight-line distance at city speed, not road routing.
- The ER wait is a rough estimate from how full the ER is, not a measured wait.
- Staff login pages are placeholders.
