"use client";

import "../effects.css";
import { useEffect, useMemo, useState } from "react";
import { STATUS, formatWait } from "../geo";
import type { Hospital, Incident, Status } from "../types";

interface TickerItem {
  key: string;
  status: Status;
  text: string;
}

function items(hospitals: Hospital[], incidents: Incident[]): TickerItem[] {
  const out: TickerItem[] = incidents.map((i) => ({ key: i.id, status: "critical", text: `Incident: ${i.summary}` }));
  const byWait = [...hospitals].sort((a, b) => a.er_wait_min - b.er_wait_min);
  for (const h of hospitals.filter((x) => x.status === "critical")) {
    out.push({ key: `full-${h.id}`, status: "critical", text: `${h.name} is at capacity · ER wait ${formatWait(h.er_wait_min)}` });
  }
  for (const h of byWait.filter((x) => x.status === "open").slice(0, 3)) {
    out.push({ key: `open-${h.id}`, status: "open", text: `${h.name} is accepting patients · ER wait ${formatWait(h.er_wait_min)}` });
  }
  for (const h of hospitals.filter((x) => x.status === "busy").slice(0, 2)) {
    out.push({ key: `busy-${h.id}`, status: "busy", text: `${h.name} is busy · ${h.er.capacity - h.er.occupied} ER bays open` });
  }
  return out;
}

/** One line of live news that rotates every few seconds. */
export function LiveTicker({
  hospitals,
  incidents = [],
  intervalMs = 3800,
  className = "",
}: {
  hospitals: Hospital[];
  incidents?: Incident[];
  intervalMs?: number;
  className?: string;
}) {
  const list = useMemo(() => items(hospitals, incidents), [hospitals, incidents]);
  const [tick, setTick] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setTick((n) => n + 1), intervalMs);
    return () => clearInterval(t);
  }, [intervalMs]);

  if (!list.length) return null;
  const item = list[tick % list.length];
  return (
    <div className={`flex min-w-0 items-center gap-2.5 overflow-hidden text-[13px] ${className}`} aria-live="polite">
      <span className="shrink-0 rounded bg-white/10 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-widest text-sky-200">Live</span>
      <p key={`${tick}-${item.key}`} className="emf-tick flex min-w-0 items-center gap-2">
        <span className="size-1.5 shrink-0 rounded-full" style={{ background: STATUS[item.status].color }} />
        <span className="truncate text-slate-200">{item.text}</span>
      </p>
    </div>
  );
}
