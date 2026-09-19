"use client";

import "../effects.css";
import { STATUS } from "../geo";
import type { SimulationState } from "../use-simulation";
import type { Hospital, Simulation } from "../types";

const CASUALTY_PRESETS = [15, 40, 80];

function Stat({ label, a, b, unit = "min" }: { label: string; a: number; b: number; unit?: string }) {
  const better = a < b;
  return (
    <div className="grid grid-cols-[minmax(0,1fr)_64px_64px] items-baseline gap-2 py-1.5 text-[13px]">
      <span className="text-slate-500">{label}</span>
      <span className={`text-right font-semibold tabular-nums ${better ? "text-emerald-700" : "text-slate-900"}`}>
        {a}
        {unit && <span className="text-[11px] font-normal text-slate-400"> {unit}</span>}
      </span>
      <span className="text-right tabular-nums text-slate-500">
        {b}
        {unit && <span className="text-[11px] text-slate-400"> {unit}</span>}
      </span>
    </div>
  );
}

/** Casualties still without a bed over time: coordinated vs. everyone to the nearest trauma center. */
function WaitingChart({ sim, frame }: { sim: Simulation; frame: number }) {
  const w = 320;
  const h = 96;
  const pad = { l: 22, r: 6, t: 8, b: 16 };
  const frames = sim.frames;
  const maxMin = frames[frames.length - 1].minute;
  const maxY = Math.max(1, ...frames.map((f) => Math.max(f.without_bed.coordinated, f.without_bed.nearest)));
  const x = (m: number) => pad.l + (m / maxMin) * (w - pad.l - pad.r);
  const y = (v: number) => pad.t + (1 - v / maxY) * (h - pad.t - pad.b);
  const line = (key: "coordinated" | "nearest") => frames.map((f, i) => `${i ? "L" : "M"}${x(f.minute)},${y(f.without_bed[key])}`).join("");
  const cur = frames[frame];

  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full" role="img" aria-label="Casualties without a bed over time">
      <defs>
        <linearGradient id="emf-area" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#6366f1" stopOpacity={0.25} />
          <stop offset="1" stopColor="#6366f1" stopOpacity={0} />
        </linearGradient>
      </defs>
      {[0, maxY].map((v) => (
        <g key={v}>
          <line x1={pad.l} x2={w - pad.r} y1={y(v)} y2={y(v)} stroke="#e2e8f0" />
          <text x={pad.l - 5} y={y(v) + 3} textAnchor="end" className="fill-slate-400 text-[9px] tabular-nums">
            {v}
          </text>
        </g>
      ))}
      {[0, 60, 120, 180].filter((m) => m <= maxMin).map((m) => (
        <text key={m} x={x(m)} y={h - 3} textAnchor="middle" className="fill-slate-400 text-[9px]">
          {m === 0 ? "0" : `${m / 60}h`}
        </text>
      ))}
      <path d={line("nearest")} fill="none" stroke="#ef4444" strokeWidth={1.75} strokeDasharray="4 3" />
      <path d={`${line("coordinated")}L${x(maxMin)},${y(0)}L${x(0)},${y(0)}Z`} fill="url(#emf-area)" stroke="none" />
      <path d={line("coordinated")} fill="none" stroke="#4f46e5" strokeWidth={2} />
      <line x1={x(cur.minute)} x2={x(cur.minute)} y1={pad.t} y2={h - pad.b} stroke="#94a3b8" strokeDasharray="2 2" />
      <circle cx={x(cur.minute)} cy={y(cur.without_bed.nearest)} r={3} fill="#ef4444" />
      <circle cx={x(cur.minute)} cy={y(cur.without_bed.coordinated)} r={3} fill="#4f46e5" />
    </svg>
  );
}

/** How much faster the swarm's plan got casualties to a bed, or null if it wasn't faster. */
function speedup(sim: Simulation) {
  const { coordinated: c, nearest: n } = sim.comparison;
  if (c.avg_to_bed_min >= n.avg_to_bed_min) return null;
  return {
    minutes: n.avg_to_bed_min - c.avg_to_bed_min,
    percent: Math.round((1 - c.avg_to_bed_min / n.avg_to_bed_min) * 100),
    fewerWaiting: n.without_bed - c.without_bed,
  };
}

/**
 * The what-if simulator: place an incident, choose its size, then compare the swarm's plan with
 * sending everyone to the nearest trauma center. Pair with SimulationTimeline on the map.
 */
export function SimulationPanel({
  sim,
  hospitals,
  recorded = false,
  className = "",
}: {
  sim: SimulationState;
  /** Hospitals in the current frame, for names and live status. */
  hospitals: Hospital[];
  /** True when the data source is a recording: the recorded scenario plays wherever you click. */
  recorded?: boolean;
  className?: string;
}) {
  const byId = Object.fromEntries(hospitals.map((h) => [h.id, h]));
  const result = sim.result;
  const gain = result ? speedup(result) : null;

  return (
    <div className={`flex flex-col ${className}`}>
      <div className="flex items-start justify-between gap-3 border-b border-red-100 bg-linear-to-r from-red-50 to-orange-50 px-4 py-3">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-wide text-red-600">What-if simulation</p>
          <h2 className="mt-0.5 text-sm font-semibold text-slate-900">
            {result ? `${result.incident.casualties} casualties, ${result.assignments.length} hospitals` : "Mass casualty incident"}
          </h2>
        </div>
        <button type="button" onClick={sim.exit} className="rounded-md px-2 py-1 text-xs font-medium text-slate-500 hover:bg-white hover:text-slate-900">
          Exit
        </button>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto">
        {sim.phase === "placing" && (
          <div className="px-4 py-6 text-center">
            <p className="text-sm font-medium text-slate-900">Click anywhere on the map</p>
            <p className="mt-1 text-[13px] leading-relaxed text-slate-500">
              That&apos;s where the incident happens. The swarm will decide where every casualty should go, based on how full each
              hospital is right now.
            </p>
          </div>
        )}

        {(sim.phase === "ready" || sim.phase === "error" || sim.phase === "loading") && (
          <div className="space-y-4 px-4 py-4">
            <div>
              <div className="flex items-baseline justify-between">
                <label htmlFor="emf-casualties" className="text-[13px] font-medium text-slate-700">
                  Casualties
                </label>
                <span className="text-lg font-semibold tabular-nums text-slate-900">{sim.casualties}</span>
              </div>
              <input
                id="emf-casualties"
                type="range"
                min={5}
                max={120}
                step={5}
                value={sim.casualties}
                onChange={(e) => sim.setCasualties(Number(e.target.value))}
                className="mt-2 w-full accent-red-600"
              />
              <div className="mt-2 flex gap-1.5">
                {CASUALTY_PRESETS.map((n) => (
                  <button
                    key={n}
                    type="button"
                    onClick={() => sim.setCasualties(n)}
                    className={`rounded-md px-2 py-1 text-xs font-medium ring-1 ring-inset transition ${sim.casualties === n ? "bg-red-600 text-white ring-red-600" : "text-slate-600 ring-slate-200 hover:bg-red-50"}`}
                  >
                    {n === 15 ? "Bus crash · 15" : n === 40 ? "Pileup · 40" : "Stadium · 80"}
                  </button>
                ))}
              </div>
            </div>
            {recorded && (
              <p className="rounded-md bg-amber-50 px-3 py-2 text-xs leading-relaxed text-amber-800">
                The swarm server isn&apos;t running, so this plays a recorded scenario (60 casualties downtown).
              </p>
            )}
            {sim.error && <p className="rounded-md bg-red-50 px-3 py-2 text-xs text-red-700">{sim.error}</p>}
            <button
              type="button"
              onClick={sim.run}
              disabled={sim.phase === "loading"}
              className="w-full rounded-lg bg-linear-to-r from-red-600 to-orange-500 px-3 py-2.5 text-sm font-semibold text-white shadow-md shadow-red-600/20 transition hover:brightness-110 disabled:opacity-70"
            >
              {sim.phase === "loading" ? "Simulating every hospital…" : "Run simulation"}
            </button>
            <p className="text-center text-xs text-slate-400">Click the map again to move the incident.</p>
          </div>
        )}

        {result && (sim.phase === "playing" || sim.phase === "paused") && (
          <div className="px-4 py-4">
            {gain && (
              <div className="emf-pop mb-4 rounded-xl bg-linear-to-br from-indigo-600 via-indigo-500 to-sky-500 px-4 py-3 text-white shadow-md shadow-indigo-600/20">
                <p className="text-[11px] font-medium uppercase tracking-wider text-indigo-100">With EmerFlow coordination</p>
                <p className="mt-0.5 flex items-baseline gap-2">
                  <span className="text-3xl font-bold tabular-nums tracking-tight">{gain.percent}%</span>
                  <span className="text-sm font-medium text-indigo-50">faster to a bed</span>
                </p>
                <p className="mt-0.5 text-xs text-indigo-100">
                  {gain.minutes} min sooner on average
                  {gain.fewerWaiting > 0 && ` · ${gain.fewerWaiting} fewer still waiting after 3 h`}
                </p>
              </div>
            )}
            <div className="grid grid-cols-[minmax(0,1fr)_64px_64px] gap-2 border-b border-slate-100 pb-1.5 text-[11px] font-medium text-slate-400">
              <span>After 3 hours</span>
              <span className="text-right text-indigo-700">EmerFlow</span>
              <span className="text-right">Nearest only</span>
            </div>
            <Stat label="Avg. time to a bed" a={result.comparison.coordinated.avg_to_bed_min} b={result.comparison.nearest.avg_to_bed_min} />
            <Stat label="Longest wait" a={result.comparison.coordinated.longest_to_bed_min} b={result.comparison.nearest.longest_to_bed_min} />
            <Stat label="Still without a bed" a={result.comparison.coordinated.without_bed} b={result.comparison.nearest.without_bed} unit="" />
            <p className="mt-2 text-xs leading-relaxed text-slate-400">
              &ldquo;Nearest only&rdquo; sends every casualty to {result.comparison.nearest.hospital}, the closest trauma center.
            </p>

            <div className="mt-4">
              <div className="flex items-center justify-between text-xs">
                <span className="font-medium text-slate-700">Casualties without a bed</span>
                <span className="flex items-center gap-3 text-slate-400">
                  <span className="flex items-center gap-1">
                    <span className="h-0.5 w-3 bg-indigo-600" /> EmerFlow
                  </span>
                  <span className="flex items-center gap-1">
                    <span className="h-0.5 w-3 border-t-2 border-dashed border-red-500" /> Nearest
                  </span>
                </span>
              </div>
              <WaitingChart sim={result} frame={sim.frame} />
            </div>

            <p className="mt-4 text-xs font-medium text-slate-700">Where the swarm sent them</p>
            <ul className="mt-1 divide-y divide-slate-100">
              {result.assignments.map((a) => {
                const h = byId[a.hospital_id];
                if (!h) return null;
                return (
                  <li key={a.hospital_id} className="flex items-center justify-between gap-3 py-2 text-[13px]">
                    <span className="flex min-w-0 items-center gap-2">
                      <span className="size-1.5 shrink-0 rounded-full transition-colors" style={{ background: STATUS[h.status].color }} />
                      <span className="truncate text-slate-700">{h.name}</span>
                    </span>
                    <span className="shrink-0 tabular-nums text-slate-500">
                      <b className="font-semibold text-slate-900">{a.casualties}</b>
                      {a.severe > 0 && <span className="text-red-600"> · {a.severe} severe</span>} · {a.drive_min} min
                    </span>
                  </li>
                );
              })}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}

/** Play/pause and a scrubber for a finished simulation. Designed to sit over the bottom of the map. */
export function SimulationTimeline({ sim, className = "" }: { sim: SimulationState; className?: string }) {
  const result = sim.result;
  if (!result || (sim.phase !== "playing" && sim.phase !== "paused")) return null;
  const f = result.frames[sim.frame];
  const playing = sim.phase === "playing";
  return (
    <div className={`flex items-center gap-3 rounded-xl bg-linear-to-r from-indigo-950/95 to-slate-900/95 px-3 py-2.5 text-white shadow-lg ring-1 ring-white/10 backdrop-blur ${className}`}>
      <button
        type="button"
        onClick={playing ? sim.pause : sim.play}
        aria-label={playing ? "Pause" : "Play"}
        className="grid size-8 shrink-0 place-items-center rounded-full bg-linear-to-br from-sky-300 to-indigo-300 text-indigo-950 transition hover:brightness-110"
      >
        {playing ? (
          <svg viewBox="0 0 24 24" className="size-3.5" fill="currentColor" aria-hidden>
            <rect x="6" y="5" width="4" height="14" rx="1" />
            <rect x="14" y="5" width="4" height="14" rx="1" />
          </svg>
        ) : (
          <svg viewBox="0 0 24 24" className="ml-0.5 size-3.5" fill="currentColor" aria-hidden>
            <path d="M7 5.5v13a1 1 0 0 0 1.5.86l11-6.5a1 1 0 0 0 0-1.72l-11-6.5A1 1 0 0 0 7 5.5Z" />
          </svg>
        )}
      </button>
      <div className="min-w-0 flex-1">
        <div className="flex items-baseline justify-between text-xs">
          <span className="font-semibold tabular-nums">
            {f.minute === 0 ? "Incident" : `+${f.minute >= 60 ? `${Math.floor(f.minute / 60)}h ${f.minute % 60 ? `${f.minute % 60}m` : ""}` : `${f.minute} min`}`}
          </span>
          <span className="tabular-nums text-slate-300">
            {f.without_bed.coordinated} without a bed · <span className="text-red-300">{f.without_bed.nearest} if nearest only</span>
          </span>
        </div>
        <input
          type="range"
          min={0}
          max={result.frames.length - 1}
          value={sim.frame}
          onChange={(e) => sim.seek(Number(e.target.value))}
          aria-label="Time since incident"
          className="mt-1 w-full accent-sky-300"
        />
      </div>
    </div>
  );
}

/** A callout for the end of the playback: the result in one line. Sits over the map. */
export function SimulationVerdict({ sim, className = "" }: { sim: SimulationState; className?: string }) {
  const result = sim.result;
  if (!result || sim.phase !== "paused" || sim.frame < result.frames.length - 1) return null;
  const s = speedup(result);
  return (
    <div className={`emf-pop flex items-center gap-3 rounded-xl bg-white/95 px-4 py-3 shadow-xl ring-1 ring-slate-900/5 backdrop-blur ${className}`}>
      <span className={`grid size-9 shrink-0 place-items-center rounded-full text-white ${s ? "bg-linear-to-br from-emerald-500 to-teal-500" : "bg-slate-400"}`}>
        <svg viewBox="0 0 24 24" className="size-5" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
          <path d="m5 12 5 5L20 7" />
        </svg>
      </span>
      <div className="min-w-0">
        <p className="text-sm font-semibold text-slate-900">
          {s ? `${s.percent}% faster to a bed with EmerFlow` : "Same outcome as sending everyone to the nearest trauma center"}
        </p>
        <p className="text-xs text-slate-500">
          {s
            ? `${result.comparison.coordinated.avg_to_bed_min} min on average vs ${result.comparison.nearest.avg_to_bed_min} min if everyone went to ${result.comparison.nearest.hospital}`
            : "Coordination didn't change waits for this incident."}
        </p>
      </div>
    </div>
  );
}
