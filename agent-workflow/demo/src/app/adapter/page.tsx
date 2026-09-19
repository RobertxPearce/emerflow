"use client";

import { useState } from "react";
import {
  DecisionLog,
  StepDetails,
  WorkflowCanvas,
  pushSource,
  useSwarmRun,
  type SwarmEvent,
  type WorkflowDefinition,
} from "@hospital-swarm/agent-workflow";
import { DemoNav } from "@/components/demo-nav";

// Example: data in a completely different shape, with a different graph.
// This is the template for plugging in a partner's data later.

// 1. The partner's own format (made up for this example).
type PartnerUpdate = { agent: string; state: "working" | "finished" | "needs-review"; note: string; details?: string[]; why?: string };

// 2. The graph to draw. No positions: the UI lays it out.
const partnerWorkflow: WorkflowDefinition = {
  steps: [
    { id: "intake", kind: "trigger", title: "Patient Intake", role: "A new patient arrives." },
    { id: "triage", kind: "ai", title: "Triage Agent", role: "Scores how urgent the patient is." },
    { id: "records", kind: "ai", title: "Records Agent", role: "Pulls the patient's history." },
    { id: "doctor", kind: "human", title: "Doctor Sign-off", role: "A doctor approves the plan." },
  ],
  edges: [
    { source: "intake", target: "triage" },
    { source: "intake", target: "records" },
    { source: "triage", target: "doctor" },
    { source: "records", target: "doctor" },
  ],
};

// 3. The adapter: partner format → protocol event. This is the only glue code needed.
function toSwarmEvent(u: PartnerUpdate): SwarmEvent {
  if (u.state === "working") return { type: "step", id: u.agent, status: "running" };
  return {
    type: "step",
    id: u.agent,
    status: u.state === "needs-review" ? "flagged" : "done",
    summary: u.note,
    input: [],
    output: u.details ?? [],
    reasoning: u.why ?? null,
  };
}

// Scripted updates standing in for a partner's API or websocket.
const script: [number, PartnerUpdate][] = [
  [0, { agent: "intake", state: "working", note: "" }],
  [600, { agent: "intake", state: "finished", note: "Chest pain, age 64", details: ["Arrived by ambulance 21:52"] }],
  [700, { agent: "triage", state: "working", note: "" }],
  [700, { agent: "records", state: "working", note: "" }],
  [1600, { agent: "triage", state: "finished", note: "Severity 2", details: ["ECG abnormal", "Stable vitals"], why: "Abnormal ECG with stable vitals." }],
  [2200, { agent: "records", state: "needs-review", note: "Allergy lists disagree", details: ["Clinic: penicillin allergy", "Hospital B: no allergies"], why: "Two sources disagree; a person must check." }],
  [2400, { agent: "doctor", state: "working", note: "" }],
  [3400, { agent: "doctor", state: "finished", note: "Admit to step-down", details: ["Allergy confirmed with patient"] }],
];

export default function AdapterExample() {
  const [{ source, push }] = useState(pushSource); // created once
  const swarm = useSwarmRun({ source, workflow: partnerWorkflow });

  function run() {
    swarm.start();
    push({ type: "meta", protocol: 1 });
    push({ type: "workflow", ...partnerWorkflow });
    script.forEach(([ms, update], i) =>
      setTimeout(() => {
        push(toSwarmEvent(update));
        if (i === script.length - 1) push({ type: "end" });
      }, ms),
    );
  }

  return (
    <main className="mx-auto max-w-[1400px] space-y-4 p-4 sm:p-6">
      <DemoNav />
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-[15px] font-semibold text-slate-900">Different data, same components</h1>
          <p className="text-[13px] text-slate-600">
            A made-up partner format is converted by one function (<code className="font-mono text-[12px]">toSwarmEvent</code>) and
            pushed in from page code. No server. See <code className="font-mono text-[12px]">demo/src/app/adapter/page.tsx</code>.
          </p>
        </div>
        <button
          type="button"
          onClick={run}
          disabled={swarm.phase === "running"}
          className="rounded bg-slate-900 px-3.5 py-2 text-[13px] font-semibold text-white hover:bg-slate-800 disabled:opacity-60"
        >
          {swarm.phase === "running" ? "Receiving updates…" : "Play partner updates"}
        </button>
      </div>
      <WorkflowCanvas swarm={swarm} className="h-[340px]" />
      <div className="grid gap-4 lg:grid-cols-2">
        <DecisionLog swarm={swarm} className="lg:self-start" />
        <StepDetails swarm={swarm} className="lg:self-start" />
      </div>
    </main>
  );
}
