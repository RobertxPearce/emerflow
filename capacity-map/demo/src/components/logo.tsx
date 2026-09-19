import Link from "next/link";

export function Logo() {
  return (
    <Link href="/" className="flex items-center gap-2">
      <span className="grid size-7 place-items-center rounded-md bg-linear-to-br from-indigo-600 to-sky-500 text-white shadow-sm shadow-indigo-600/30">
        <svg viewBox="0 0 24 24" className="size-4" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
          <path d="M3 12h4l2.5-6 5 12L17 12h4" />
        </svg>
      </span>
      <span className="text-[15px] font-semibold tracking-tight text-slate-900">EmerFlow</span>
    </Link>
  );
}
