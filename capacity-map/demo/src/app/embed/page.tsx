"use client";

// Example: a partner page (an EMS dispatch console) that uses only some pieces of the package,
// with its own layout and its own data source.

import { useMemo, useState } from "react";
import {
  CapacityMap,
  HospitalList,
  STATUS,
  rankHospitals,
  recordedSource,
  swarmSource,
  useRegion,
  withFallback,
  type LatLon,
} from "@hospital-swarm/capacity-map";
import Link from "next/link";

const source = withFallback(swarmSource({ url: "http://localhost:8000" }), recordedSource());
const UNIT: LatLon = [39.3085, -76.6177]; // Medic 14, parked in Mount Vernon

export default function DispatchConsole() {
  const { data, kind } = useRegion(source, { refreshMs: 15_000 });
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const ranked = useMemo(() => (data ? rankHospitals(data.hospitals, UNIT, "fastest") : []), [data]);
  const best = ranked.find((h) => h.status !== "critical");

  return (
    <div className="min-h-screen bg-slate-950 p-4 text-slate-100 sm:p-6">
      <header className="flex items-center justify-between">
        <div>
          <p className="text-xs font-medium uppercase tracking-widest text-slate-400">Metro Dispatch · Unit Medic 14</p>
          <h1 className="mt-1 text-xl font-semibold">Destination board</h1>
        </div>
        <Link href="/" className="text-xs text-slate-400 hover:text-white">
          ← Public page
        </Link>
      </header>

      {best && (
        <div className="mt-4 rounded-lg bg-emerald-500/10 px-4 py-3 ring-1 ring-emerald-500/30">
          <p className="text-xs text-emerald-300">Recommended destination</p>
          <p className="mt-0.5 font-semibold">
            {best.name} · {best.drive} min drive · ER wait {best.er_wait_min} min
          </p>
        </div>
      )}

      <div className="mt-4 grid gap-4 lg:grid-cols-[1fr_360px]">
        <CapacityMap
          className="h-[520px] rounded-lg"
          hospitals={data?.hospitals ?? []}
          incidents={data?.incidents}
          location={UNIT}
          locationLabel="Medic 14"
          selectedId={selectedId}
          onSelect={setSelectedId}
          route={best ? { to: best } : null}
        />
        <div className="h-[520px] overflow-y-auto rounded-lg bg-white text-slate-900">
          <HospitalList hospitals={ranked} audience="ems" selectedId={selectedId} onSelect={setSelectedId} bestId={best?.id} />
        </div>
      </div>
      <p className="mt-3 text-xs text-slate-500">
        Data: {kind ?? "…"} · <span style={{ color: STATUS.critical.color }}>●</span> full hospitals are skipped for the recommendation
      </p>
    </div>
  );
}
