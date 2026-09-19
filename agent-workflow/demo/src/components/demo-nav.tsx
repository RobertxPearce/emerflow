import Link from "next/link";
import type { ReactNode } from "react";

export function DemoNav({ children }: { children?: ReactNode }) {
  return (
    <nav className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-slate-300/70 bg-white px-4 py-2 text-[13px] text-slate-600 shadow-sm">
      <div className="flex gap-4">
        <span className="font-semibold text-slate-900">agent-workflow demo</span>
        <Link href="/" className="hover:text-slate-900">Full panel</Link>
        <Link href="/embed" className="hover:text-slate-900">Embedded in a dashboard</Link>
        <Link href="/adapter" className="hover:text-slate-900">Other data (adapter)</Link>
      </div>
      {children}
    </nav>
  );
}
