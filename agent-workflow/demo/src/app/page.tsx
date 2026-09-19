"use client";

import { useMemo, useState } from "react";
import { SwarmPanel, replaySource, sseSource } from "@hospital-swarm/agent-workflow";
import { DemoNav } from "@/components/demo-nav";

const SERVER = process.env.NEXT_PUBLIC_SIM_URL ?? "http://localhost:8000";

// Full-page use. The data source can be switched: the live simulation server,
// or a recorded run bundled with the package (no server needed).
export default function Home() {
  const [mode, setMode] = useState<"live" | "recorded">("live");
  const source = useMemo(() => (mode === "live" ? sseSource({ url: `${SERVER}/run` }) : replaySource()), [mode]);

  return (
    <main className="mx-auto max-w-[1600px] space-y-4 p-4 sm:p-6">
      <DemoNav>
        <label className="flex items-center gap-2">
          Data source
          <select
            value={mode}
            onChange={(e) => setMode(e.target.value as "live" | "recorded")}
            className="rounded border border-slate-300 bg-white px-2 py-1 text-slate-800"
          >
            <option value="live">Live simulation server</option>
            <option value="recorded">Recorded run (no server)</option>
          </select>
        </label>
      </DemoNav>
      <SwarmPanel
        key={mode}
        source={source}
        casualtyOptions={mode === "recorded" ? [] : undefined}
        errorHint={
          <>
            Start it with <code className="rounded bg-red-100 px-1 font-mono text-[12px]">npm run server</code>, or switch
            the data source to “Recorded run”.
          </>
        }
      />
    </main>
  );
}
