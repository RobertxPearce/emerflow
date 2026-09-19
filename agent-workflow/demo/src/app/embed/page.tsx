"use client";

import { useState } from "react";
import { StepDetails, WorkflowCanvas, sseSource, useSwarmRun, type SwarmRunSummary } from "@hospital-swarm/agent-workflow";
import { DemoNav } from "@/components/demo-nav";

const source = sseSource({ url: `${process.env.NEXT_PUBLIC_SIM_URL ?? "http://localhost:8000"}/run` });

// Example host page: a stand-in for a partner's dashboard. It owns the run,
// uses its own trigger button, places only some pieces, and reacts to the data.
export default function EmbedExample() {
  const [last, setLast] = useState<SwarmRunSummary | null>(null);
  const swarm = useSwarmRun({ source, onComplete: setLast });
  const units = swarm.snapshots.at(-1)?.units ?? [];

  return (
    <div className="min-h-screen">
      <div className="p-4 pb-0 sm:px-6">
        <DemoNav />
      </div>
      <header className="mx-4 mt-4 flex flex-wrap items-center justify-between gap-3 rounded-md bg-[#0b2545] px-6 py-3 text-white sm:mx-6">
        <div>
          <p className="text-[15px] font-semibold">Partner&apos;s dashboard</p>
          <p className="text-[11px] text-blue-100/70">Example host page using @hospital-swarm/agent-workflow</p>
        </div>
        <button
          type="button"
          onClick={() => swarm.start({ casualties: 25 })}
          disabled={swarm.phase === "running"}
          className="rounded bg-red-600 px-3.5 py-2 text-[13px] font-semibold hover:bg-red-700 disabled:opacity-60"
        >
          {swarm.phase === "running" ? "Agents working…" : "Trigger Mass Casualty Event"}
        </button>
      </header>

      <main className="grid gap-4 p-4 sm:p-6 lg:grid-cols-[1fr_440px]">
        <div className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-3 xl:grid-cols-5">
            {(units.length ? units : placeholderUnits).map((u) => (
              <div key={u.code} className="rounded-md border border-slate-300/70 bg-white p-4 shadow-sm">
                <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">{u.name}</p>
                <p className="mt-1 text-2xl font-semibold tabular-nums text-slate-900">
                  {u.capacity ? `${Math.round((u.occupied / u.capacity) * 100)}%` : "—"}
                </p>
                <p className="text-[11px] text-slate-500">{u.waiting ? `${u.waiting} waiting` : "Host's own metric card"}</p>
              </div>
            ))}
          </div>
          <div className="rounded-md border border-dashed border-slate-300 bg-white/60 p-6 text-[13px] text-slate-600">
            <p className="font-semibold text-slate-800">Rest of the partner&apos;s page goes here.</p>
            <p className="mt-1">
              {last
                ? `onComplete fired: seed ${last.meta?.seed}. ${last.results.outcome?.summary ?? ""}`
                : "The cards above read swarm.snapshots; this box updates through onComplete when a run ends."}
            </p>
            {swarm.error && <p className="mt-2 text-red-700">{swarm.error}</p>}
          </div>
        </div>

        <aside className="space-y-4">
          <WorkflowCanvas swarm={swarm} layout="vertical" className="h-[560px]" />
          <StepDetails swarm={swarm} />
        </aside>
      </main>
    </div>
  );
}

const placeholderUnits = ["Emergency", "Intensive Care", "Step-Down", "Surgery", "General Beds"].map((name) => ({
  code: name,
  name,
  occupied: 0,
  capacity: 0,
  waiting: 0,
}));
