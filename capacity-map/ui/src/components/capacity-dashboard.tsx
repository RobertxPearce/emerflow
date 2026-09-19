"use client";

import "../effects.css";
import { type CSSProperties, useMemo, useRef, useState } from "react";
import { countByStatus, formatTime, miles, rankHospitals } from "../geo";
import { swarmSource, withFallback, type RegionSource } from "../sources";
import type { Audience, LatLon, SortBy, Status } from "../types";
import { useLocation } from "../use-location";
import { useRegion } from "../use-region";
import { useSimulation } from "../use-simulation";
import { useWeatherAlerts } from "../use-weather-alerts";
import { CapacityMap } from "./capacity-map";
import { HospitalList } from "./hospital-list";
import { NewsFeed } from "./news-feed";
import { LiveTicker } from "./live-ticker";
import { RegionStats, type StatPick } from "./region-stats";
import { SimulationPanel, SimulationTimeline, SimulationVerdict } from "./simulation-panel";
import { StatusLegend } from "./status-legend";

const MAX_REGION_MILES = 60; // farther than this, distances are measured from the region's center
const defaultSource = withFallback(swarmSource());
/** The one-click demo: a crowd crush after a game at the stadium downtown. */
const DEMO_INCIDENT = { point: [39.278, -76.6227] as LatLon, casualties: 80 };

const delay = (ms: number) => ({ "--emf-delay": `${ms}ms` }) as CSSProperties;

/** A heartbeat trace with a pulse running along it, for the hero background. */
function HeartbeatLine() {
  const d = "M0 60 H250 l14 -4 l10 8 l12 -46 l14 78 l12 -44 l10 8 H620 l14 -4 l10 8 l12 -46 l14 78 l12 -44 l10 8 H1000";
  return (
    <svg viewBox="0 0 1000 120" preserveAspectRatio="none" className="pointer-events-none absolute inset-x-0 bottom-24 -z-10 h-28 w-full opacity-60" aria-hidden>
      <defs>
        <linearGradient id="emf-ecg" x1="0" x2="1">
          <stop offset="0" stopColor="#38bdf8" stopOpacity="0" />
          <stop offset="0.5" stopColor="#7dd3fc" />
          <stop offset="1" stopColor="#818cf8" stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={d} fill="none" stroke="rgb(125 211 252 / 0.12)" strokeWidth="1.5" vectorEffect="non-scaling-stroke" />
      <path d={d} fill="none" stroke="url(#emf-ecg)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className="emf-ecg-pulse" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

function Segmented<T extends string>({
  value,
  options,
  onChange,
  label,
  tone = "light",
}: {
  value: T;
  options: [T, string][];
  onChange: (v: T) => void;
  label: string;
  tone?: "light" | "dark";
}) {
  const dark = tone === "dark";
  return (
    <div role="radiogroup" aria-label={label} className={`flex rounded-lg p-0.5 text-xs font-medium ${dark ? "bg-white/10 ring-1 ring-white/10" : "bg-slate-100"}`}>
      {options.map(([v, text]) => (
        <button
          key={v}
          type="button"
          role="radio"
          aria-checked={value === v}
          onClick={() => onChange(v)}
          className={`rounded-md px-2.5 py-1 transition ${
            value === v
              ? dark
                ? "bg-white text-indigo-950 shadow-sm"
                : "bg-white text-indigo-700 shadow-sm"
              : dark
                ? "text-slate-300 hover:text-white"
                : "text-slate-500 hover:text-slate-900"
          }`}
        >
          {text}
        </button>
      ))}
    </div>
  );
}

export interface CapacityDashboardProps {
  /** Where data comes from. Default: the swarm server at localhost:8000, recorded data if it's down. */
  source?: RegionSource;
  title?: string;
  subtitle?: string;
  showNews?: boolean;
  showSimulator?: boolean;
}

/** The whole public page body: stats, map, closest hospitals, simulator and news. */
export function CapacityDashboard({
  source = defaultSource,
  title = "Emergency care near you",
  subtitle = "How busy nearby emergency departments are right now.",
  showNews = true,
  showSimulator: showSimulatorProp = true,
}: CapacityDashboardProps) {
  const showSimulator = showSimulatorProp && !!source.simulate;
  const region = useRegion(source);
  const sim = useSimulation(source);
  const loc = useLocation();
  const [audience, setAudience] = useState<Audience>("public");
  const [sortBy, setSortBy] = useState<SortBy>("nearest");
  const [visible, setVisible] = useState<Record<Status, boolean>>({ open: true, busy: true, critical: true });
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const mapSection = useRef<HTMLElement>(null);

  const runDemo = () => {
    setSelectedId(null);
    sim.start(DEMO_INCIDENT.point, DEMO_INCIDENT.casualties);
    mapSection.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  };
  const pickStat = (pick: StatPick) =>
    setVisible(
      pick === "accepting"
        ? { open: true, busy: true, critical: false }
        : pick === "full"
          ? { open: false, busy: false, critical: true }
          : { open: true, busy: true, critical: true },
    );

  const data = region.data;
  const simulating = sim.phase !== "off";
  const frame = sim.result && (sim.phase === "playing" || sim.phase === "paused") ? sim.result.frames[sim.frame] : null;
  const hospitals = useMemo(() => frame?.hospitals ?? data?.hospitals ?? [], [frame, data]);

  const center = data?.region.center;
  const inRegion = !!(loc.coords && center && miles(loc.coords, center) <= MAX_REGION_MILES);
  const location: LatLon | null = inRegion ? loc.coords : (center ?? null);
  const alerts = useWeatherAlerts(location);

  const ranked = useMemo(() => (location ? rankHospitals(hospitals, location, sortBy) : []), [hospitals, location, sortBy]);
  const shown = ranked.filter((h) => visible[h.status]);
  const best = useMemo(() => (location ? rankHospitals(hospitals, location, "fastest")[0] : undefined), [hospitals, location]);
  const counts = countByStatus(hospitals);

  const locationNote = inRegion
    ? "From your location"
    : loc.state === "granted"
      ? `You're outside ${data?.region.name ?? "the demo area"}; measured from downtown`
      : "Measured from downtown";

  return (
    <div>
      {/* Hero */}
      <section className="relative isolate overflow-hidden rounded-2xl bg-linear-to-br from-indigo-950 via-slate-900 to-sky-900 px-5 py-6 text-white shadow-xl shadow-indigo-950/15 sm:px-8 sm:py-9">
        <div className="pointer-events-none absolute -right-24 -top-32 -z-10 size-96 motion-safe:animate-pulse rounded-full bg-sky-500/25 blur-3xl [animation-duration:6s]" />
        <div className="pointer-events-none absolute -bottom-40 left-1/4 -z-10 size-96 motion-safe:animate-pulse rounded-full bg-indigo-500/25 blur-3xl [animation-duration:8s]" />
        <div
          className="pointer-events-none absolute inset-0 -z-10 opacity-[0.07]"
          style={{ backgroundImage: "radial-gradient(circle at 1px 1px, white 1px, transparent 0)", backgroundSize: "22px 22px" }}
        />
        <HeartbeatLine />

        <div className="flex flex-col items-start gap-5 sm:flex-row sm:justify-between">
          <div className="min-w-0 max-w-2xl">
            <p className="emf-rise flex items-center gap-2 text-[13px] text-sky-200/90">
              <span className="relative flex size-1.5">
                {region.kind === "live" && <span className="absolute inline-flex size-full animate-ping rounded-full bg-emerald-400 opacity-75" />}
                <span className={`relative inline-flex size-1.5 rounded-full ${region.kind === "live" ? "bg-emerald-400" : "bg-slate-400"}`} />
              </span>
              {data
                ? `${region.kind === "live" ? "Live from the swarm" : "Recorded snapshot"} · ${data.region.name} · Updated ${formatTime(data.generated_at)}`
                : region.error
                  ? "Can't reach the capacity feed"
                  : "Loading…"}
            </p>
            <h1 className="emf-rise mt-3 text-3xl font-semibold tracking-tight sm:text-[40px] sm:leading-[1.1]" style={delay(60)}>
              {title.split(" ").slice(0, -2).join(" ")}{" "}
              <span className="bg-linear-to-r from-sky-300 via-cyan-200 to-indigo-300 bg-clip-text text-transparent">{title.split(" ").slice(-2).join(" ")}</span>
            </h1>
            <p className="emf-rise mt-2 text-[15px] text-slate-300 sm:text-base" style={delay(120)}>
              {subtitle}
            </p>
            <div className="emf-rise mt-5 flex flex-wrap items-center gap-2.5" style={delay(180)}>
              {showSimulator && (
                <button
                  type="button"
                  onClick={runDemo}
                  className="emf-shine inline-flex items-center gap-2 rounded-lg bg-linear-to-r from-red-500 to-orange-500 px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-red-500/30 transition hover:-translate-y-0.5 hover:shadow-xl hover:shadow-red-500/40 active:translate-y-0"
                >
                  <svg viewBox="0 0 24 24" className="size-4" fill="currentColor" aria-hidden>
                    <path d="M7 5.5v13a1 1 0 0 0 1.5.86l11-6.5a1 1 0 0 0 0-1.72l-11-6.5A1 1 0 0 0 7 5.5Z" />
                  </svg>
                  Run the crisis demo
                  <span className="hidden font-normal text-red-50/90 sm:inline">· {DEMO_INCIDENT.casualties} casualties</span>
                </button>
              )}
              {loc.state !== "granted" && (
                <button
                  type="button"
                  onClick={loc.locate}
                  disabled={loc.state === "asking"}
                  className="inline-flex items-center gap-2 rounded-lg bg-white/10 px-4 py-2.5 text-sm font-medium text-white ring-1 ring-white/20 backdrop-blur transition hover:-translate-y-0.5 hover:bg-white/15 disabled:opacity-60"
                >
                  <svg viewBox="0 0 24 24" className="size-4" fill="none" stroke="currentColor" strokeWidth="2.2" aria-hidden>
                    <circle cx="12" cy="12" r="3" />
                    <path d="M12 2v3M12 19v3M2 12h3M19 12h3" />
                  </svg>
                  {loc.state === "asking" ? "Locating…" : "Find care near me"}
                </button>
              )}
            </div>
          </div>
          <div className="emf-rise shrink-0" style={delay(200)}>
            <Segmented
              label="View"
              tone="dark"
              value={audience}
              onChange={setAudience}
              options={[
                ["public", "Public"],
                ["ems", "EMS crew"],
              ]}
            />
          </div>
        </div>

        {data && <LiveTicker hospitals={hospitals} incidents={simulating ? [] : data.incidents} className="emf-rise mt-6" />}
        <RegionStats hospitals={hospitals} tone="dark" onPick={pickStat} className="mt-4" />
      </section>

      {!simulating &&
        data?.incidents.map((i) => (
          <p key={i.id} className="mt-4 flex items-start gap-2.5 rounded-lg border-l-4 border-red-500 bg-linear-to-r from-red-50 to-orange-50/40 px-3.5 py-2.5 text-[13px] leading-relaxed text-red-800">
            <span className="relative mt-[5px] flex size-2 shrink-0">
              <span className="absolute inline-flex size-full animate-ping rounded-full bg-red-400 opacity-75" />
              <span className="relative inline-flex size-2 rounded-full bg-red-500" />
            </span>
            <span>
              <span className="font-semibold">Mass casualty incident</span> · {i.title}. {i.summary}
            </span>
          </p>
        ))}

      {/* Map + side panel */}
      <section ref={mapSection} className="emf-rise mt-4 grid scroll-mt-20 gap-4 lg:grid-cols-[minmax(0,1fr)_380px]" style={delay(300)}>
        <CapacityMap
          className="h-[440px] rounded-xl border border-slate-200 shadow-sm lg:h-[640px]"
          hospitals={hospitals}
          incidents={data?.incidents}
          location={location}
          locationLabel={inRegion ? "Your location" : `${data?.region.name ?? "Region"} (demo area)`}
          selectedId={selectedId}
          onSelect={setSelectedId}
          hoveredId={hoveredId}
          onHover={setHoveredId}
          visible={visible}
          route={best && !simulating ? { to: best } : null}
          simulation={
            showSimulator
              ? {
                  point: sim.point,
                  assignments: frame ? sim.result?.assignments : undefined,
                  placing: sim.phase === "placing" || sim.phase === "ready" || sim.phase === "error",
                  onPlace: sim.place,
                }
              : undefined
          }
        >
          <div className="pointer-events-none absolute inset-x-3 top-3 z-[1000] flex flex-wrap items-start justify-between gap-2">
            <StatusLegend
              className="pointer-events-auto"
              counts={counts}
              visible={visible}
              onToggle={(s) => setVisible((v) => ({ ...v, [s]: !v[s] }))}
            />
            {showSimulator && !simulating && (
              <button
                type="button"
                onClick={sim.begin}
                className="pointer-events-auto flex items-center gap-2 rounded-lg bg-linear-to-r from-red-600 to-orange-500 px-3 py-2 text-xs font-semibold text-white shadow-md shadow-red-600/25 transition hover:brightness-110"
              >
                <span className="relative flex size-2">
                  <span className="absolute inline-flex size-full animate-ping rounded-full bg-white opacity-75" />
                  <span className="relative inline-flex size-2 rounded-full bg-white" />
                </span>
                Simulate an incident
              </button>
            )}
            {sim.phase === "placing" && (
              <p className="pointer-events-auto rounded-lg bg-indigo-950 px-3 py-2 text-xs font-medium text-white shadow-md">
                Click the map to place the incident
              </p>
            )}
          </div>
          <SimulationVerdict sim={sim} className="absolute left-1/2 top-16 z-[1000] w-[min(92%,460px)] -translate-x-1/2" />
          <SimulationTimeline sim={sim} className="absolute inset-x-3 bottom-8 z-[1000]" />
        </CapacityMap>

        <aside className="flex max-h-[560px] flex-col overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm lg:h-[640px] lg:max-h-none">
          {simulating ? (
            <SimulationPanel sim={sim} hospitals={hospitals} recorded={region.kind === "recorded"} className="min-h-0 flex-1" />
          ) : (
            <>
              <div className="border-b border-indigo-100 bg-linear-to-r from-indigo-50 to-sky-50 px-4 py-3">
                <div className="flex items-center justify-between gap-3">
                  <h2 className="text-sm font-semibold text-slate-900">{sortBy === "fastest" ? "Fastest care" : "Closest hospitals"}</h2>
                  <Segmented
                    label="Sort hospitals"
                    value={sortBy}
                    onChange={setSortBy}
                    options={[
                      ["nearest", "Nearest"],
                      ["fastest", "Fastest"],
                    ]}
                  />
                </div>
                <div className="mt-1 flex items-center justify-between gap-3 text-xs text-slate-500">
                  <span>{sortBy === "fastest" ? "Drive time + ER wait. " : ""}{locationNote}</span>
                  {loc.state !== "granted" && (
                    <button
                      type="button"
                      onClick={loc.locate}
                      disabled={loc.state === "asking"}
                      className="inline-flex shrink-0 items-center gap-1 font-medium text-indigo-600 hover:text-indigo-800 disabled:opacity-60"
                    >
                      <svg viewBox="0 0 24 24" className="size-3.5" fill="none" stroke="currentColor" strokeWidth="2.2" aria-hidden>
                        <circle cx="12" cy="12" r="3" />
                        <path d="M12 2v3M12 19v3M2 12h3M19 12h3" />
                      </svg>
                      {loc.state === "asking" ? "Locating…" : loc.state === "denied" ? "Location blocked" : "Use my location"}
                    </button>
                  )}
                </div>
              </div>
              <div className="min-h-0 flex-1 overflow-y-auto">
                {shown.length ? (
                  <HospitalList
                    hospitals={shown}
                    audience={audience}
                    selectedId={selectedId}
                    onSelect={setSelectedId}
                    hoveredId={hoveredId}
                    onHover={setHoveredId}
                    bestId={best?.id}
                  />
                ) : data ? (
                  <p className="px-4 py-6 text-center text-[13px] text-slate-400">No hospitals match the map filter.</p>
                ) : (
                  <div className="space-y-2 p-4">
                    {Array.from({ length: 6 }, (_, i) => (
                      <div key={i} className="h-14 animate-pulse rounded-md bg-slate-100" />
                    ))}
                  </div>
                )}
              </div>
              {audience === "public" && (
                <p className="border-t border-slate-100 px-4 py-2.5 text-[11px] leading-relaxed text-slate-400">
                  For chest pain, stroke symptoms or severe injury, call 911. Paramedics choose the right hospital.
                </p>
              )}
            </>
          )}
        </aside>
      </section>

      {showNews && (
        <section className="mt-14">
          <h2 className="flex items-center gap-2.5 text-lg font-semibold tracking-tight text-slate-900">
            <span className="h-5 w-1 rounded-full bg-linear-to-b from-indigo-500 to-sky-400" />
            Local emergency news
          </h2>
          <p className="mt-0.5 text-sm text-slate-500">Incidents, hospital capacity and weather alerts for your area.</p>
          {data ? (
            <NewsFeed
              className="mt-4"
              hospitals={data.hospitals}
              incidents={data.incidents}
              alerts={alerts?.alerts ?? []}
              alertsAvailable={alerts ? alerts.available : null}
              generatedAt={data.generated_at}
            />
          ) : (
            <div className="mt-4 h-48 animate-pulse rounded-xl bg-slate-100" />
          )}
        </section>
      )}
    </div>
  );
}
