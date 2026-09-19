"use client";

import type { CSSProperties, ReactNode } from "react";
import { formatWait } from "../geo";
import type { Hospital } from "../types";
import { useCountUp } from "../use-count-up";
import "../effects.css";

/** Which stat tile was clicked: "accepting" / "full" filter the map, "all" resets it. */
export type StatPick = "accepting" | "full" | "all";

function median(values: number[]) {
  const s = [...values].sort((a, b) => a - b);
  return s.length ? s[Math.floor(s.length / 2)] : 0;
}

const icon = (d: ReactNode) => (
  <svg viewBox="0 0 24 24" className="size-4" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
    {d}
  </svg>
);

const ICONS = {
  hospital: icon(
    <>
      <path d="M4 21V5a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v16" />
      <path d="M12 7v6M9 10h6M3 21h18" />
    </>,
  ),
  alert: icon(
    <>
      <path d="M12 3 2 20h20L12 3Z" />
      <path d="M12 10v4M12 17h.01" />
    </>,
  ),
  bed: icon(
    <>
      <path d="M3 18V6M3 14h18v4M21 14v-2a3 3 0 0 0-3-3h-7v5" />
      <circle cx="7" cy="11" r="2" />
    </>,
  ),
  clock: icon(
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l3 2" />
    </>,
  ),
};

// Each tile has its own accent; "alert" tiles turn red when something needs attention.
const ACCENTS = {
  emerald: { light: "bg-emerald-50 text-emerald-600", dark: "bg-emerald-400/15 text-emerald-300" },
  red: { light: "bg-red-50 text-red-600", dark: "bg-red-400/15 text-red-300" },
  sky: { light: "bg-sky-50 text-sky-600", dark: "bg-sky-400/15 text-sky-300" },
  amber: { light: "bg-amber-50 text-amber-600", dark: "bg-amber-400/15 text-amber-300" },
};

/**
 * Four headline numbers for the region. Numbers count up when they change. `tone="dark"` for use
 * on a dark background. With `onPick`, tiles are buttons (e.g. to filter the map).
 */
export function RegionStats({
  hospitals,
  tone = "light",
  onPick,
  className = "",
}: {
  hospitals: Hospital[];
  tone?: "light" | "dark";
  onPick?: (pick: StatPick) => void;
  className?: string;
}) {
  const accepting = useCountUp(hospitals.filter((h) => h.status !== "critical").length);
  const full = useCountUp(hospitals.filter((h) => h.status === "critical").length);
  const erFree = useCountUp(hospitals.reduce((n, h) => n + Math.max(0, h.er.capacity - h.er.occupied), 0));
  const waiting = hospitals.reduce((n, h) => n + h.er.waiting + h.icu.waiting, 0);
  const wait = useCountUp(median(hospitals.map((h) => h.er_wait_min)));
  const stats = [
    { label: "Hospitals accepting", value: `${accepting}`, sub: `of ${hospitals.length}`, icon: ICONS.hospital, accent: ACCENTS.emerald, pick: "accepting" as const, hint: "Show only hospitals accepting patients" },
    { label: "At capacity", value: `${full}`, sub: full === 1 ? "hospital" : "hospitals", icon: ICONS.alert, accent: ACCENTS.red, alert: full > 0, pick: "full" as const, hint: "Show only full hospitals" },
    { label: "Open ER bays", value: `${erFree}`, sub: waiting ? `${waiting} waiting for a bed` : "no one waiting", icon: ICONS.bed, accent: ACCENTS.sky, pick: "all" as const, hint: "Show all hospitals" },
    { label: "Median ER wait", value: formatWait(wait), sub: "across the region", icon: ICONS.clock, accent: ACCENTS.amber, pick: "all" as const, hint: "Show all hospitals" },
  ];
  const dark = tone === "dark";

  return (
    <dl className={`grid grid-cols-2 gap-2 sm:grid-cols-4 sm:gap-3 ${className}`}>
      {stats.map((s, i) => (
        <div
          key={s.label}
          role={onPick ? "button" : undefined}
          tabIndex={onPick ? 0 : undefined}
          title={onPick ? s.hint : undefined}
          onClick={onPick ? () => onPick(s.pick) : undefined}
          onKeyDown={onPick ? (e) => (e.key === "Enter" || e.key === " ") && (e.preventDefault(), onPick(s.pick)) : undefined}
          style={{ "--emf-delay": `${150 + i * 70}ms` } as CSSProperties}
          className={`emf-rise group flex items-start gap-3 rounded-xl px-3.5 py-3 transition duration-200 ${
            dark ? "bg-white/[0.06] ring-1 ring-white/10 backdrop-blur" : "border border-slate-200 bg-white"
          } ${onPick ? (dark ? "cursor-pointer hover:-translate-y-0.5 hover:bg-white/[0.11] hover:ring-white/25" : "cursor-pointer hover:-translate-y-0.5 hover:shadow-md") : ""}`}
        >
          <span className={`mt-0.5 grid size-8 shrink-0 place-items-center rounded-lg transition-transform duration-200 group-hover:scale-110 ${dark ? s.accent.dark : s.accent.light}`}>
            {s.icon}
          </span>
          <div className="min-w-0">
            <dt className={`text-xs ${dark ? "text-slate-300" : "text-slate-500"}`}>{s.label}</dt>
            <dd className="mt-0.5 flex flex-wrap items-baseline gap-x-1.5">
              <span
                className={`whitespace-nowrap text-xl font-semibold tabular-nums tracking-tight transition-colors ${
                  s.alert ? (dark ? "text-red-300" : "text-red-600") : dark ? "text-white" : "text-slate-900"
                }`}
              >
                {s.value}
              </span>
              <span className="text-xs text-slate-400">{s.sub}</span>
            </dd>
          </div>
        </div>
      ))}
    </dl>
  );
}
