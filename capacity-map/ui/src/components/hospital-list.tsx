"use client";

import { type CSSProperties, useEffect, useRef } from "react";
import { STATUS, directionsUrl, formatWait, type RankedHospital } from "../geo";
import type { Audience, UnitLoad } from "../types";
import "../effects.css";

function LoadBar({ label, unit }: { label: string; unit: UnitLoad }) {
  const pct = Math.min(100, Math.round((unit.occupied / unit.capacity) * 100));
  const color = unit.waiting > 0 || pct >= 97 ? "bg-red-500" : pct >= 85 ? "bg-amber-500" : "bg-emerald-500";
  return (
    <div>
      <div className="flex justify-between text-[11px] text-slate-500">
        <span>{label}</span>
        <span className="tabular-nums">
          {unit.occupied}/{unit.capacity}
          {unit.waiting > 0 && <span className="text-red-600"> +{unit.waiting}</span>}
        </span>
      </div>
      <div className="mt-1 h-1 overflow-hidden rounded-full bg-slate-100">
        <div className={`h-full rounded-full transition-all duration-500 ${color}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

/** Hospitals in the order given (see rankHospitals). Click a row to select it. */
export function HospitalList({
  hospitals,
  audience = "public",
  selectedId,
  onSelect,
  hoveredId,
  onHover,
  bestId,
}: {
  hospitals: RankedHospital[];
  audience?: Audience;
  selectedId?: string | null;
  onSelect?: (id: string) => void;
  /** Highlight a row (e.g. while its map pin is hovered) and report hovers back. */
  hoveredId?: string | null;
  onHover?: (id: string | null) => void;
  /** Marked "Fastest care": the lowest drive + ER wait. */
  bestId?: string | null;
}) {
  const items = useRef<Record<string, HTMLLIElement | null>>({});
  useEffect(() => {
    if (selectedId) items.current[selectedId]?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [selectedId]);

  return (
    <ul className="divide-y divide-slate-100">
      {hospitals.map((h, i) => {
        const s = STATUS[h.status];
        const selected = h.id === selectedId;
        const hovered = h.id === hoveredId && !selected;
        return (
          <li
            key={h.id}
            ref={(el) => {
              items.current[h.id] = el;
            }}
            onMouseEnter={() => onHover?.(h.id)}
            onMouseLeave={() => onHover?.(null)}
            style={{ "--emf-delay": `${250 + Math.min(i, 8) * 45}ms` } as CSSProperties}
            className={`emf-rise border-l-[3px] transition-colors ${
              selected ? "border-indigo-500 bg-indigo-50/60" : hovered ? "border-indigo-300 bg-indigo-50/40" : "border-transparent"
            }`}
          >
            <button
              type="button"
              onClick={() => onSelect?.(h.id)}
              aria-pressed={selected}
              className="w-full px-4 py-3 text-left"
            >
              <div className="flex items-baseline justify-between gap-3">
                <p className="text-sm font-medium text-slate-900">
                  {h.name}
                  {h.id === bestId && (
                    <span className="ml-2 inline-block translate-y-[-1px] rounded bg-linear-to-r from-indigo-600 to-sky-500 px-1.5 py-px align-middle text-[10px] font-semibold uppercase tracking-wide text-white">
                      Fastest care
                    </span>
                  )}
                </p>
                <span className="shrink-0 text-xs tabular-nums text-slate-400">
                  {h.distance.toFixed(1)} mi · {h.drive} min
                </span>
              </div>
              <p className="mt-1 flex flex-wrap items-center gap-x-1.5 text-[13px] text-slate-500">
                <span className={`size-1.5 rounded-full transition-colors ${s.dot}`} />
                <span className={`font-medium ${s.text}`}>{s.label}</span>
                <span className="text-slate-300">·</span>
                <span>ER wait {formatWait(h.er_wait_min)}</span>
                {audience === "ems" && h.trauma && (
                  <>
                    <span className="text-slate-300">·</span>
                    <span>Trauma {h.trauma.replace("Level ", "")}</span>
                  </>
                )}
              </p>
              {h.receiving_incident && <p className="mt-1 text-xs font-medium text-red-600">Receiving incident casualties</p>}
              {audience === "ems" && (
                <div className="mt-2.5 grid grid-cols-2 gap-4">
                  <LoadBar label="ER" unit={h.er} />
                  <LoadBar label="ICU" unit={h.icu} />
                </div>
              )}
            </button>
            {selected && (
              <div className="px-4 pb-3">
                <a href={directionsUrl(h)} target="_blank" rel="noreferrer" className="text-xs font-medium text-indigo-600 hover:text-indigo-800">
                  {h.address} · Directions →
                </a>
              </div>
            )}
          </li>
        );
      })}
    </ul>
  );
}
