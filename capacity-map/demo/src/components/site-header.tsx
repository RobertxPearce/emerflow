import Link from "next/link";
import { Logo } from "./logo";

export function SiteHeader() {
  return (
    <header className="sticky top-0 z-[1100] border-b border-slate-200/70 bg-white/80 backdrop-blur-md">
      <div className="mx-auto flex h-14 max-w-7xl items-center justify-between gap-4 px-4 sm:px-6">
        <Logo />
        <nav className="flex items-center gap-1 text-sm" aria-label="Main">
          <a href="tel:911" className="mr-2 flex items-center gap-1.5 font-medium text-red-600 hover:text-red-700">
            <span className="size-1.5 rounded-full bg-red-600" />
            <span className="hidden sm:inline">Emergency? Call</span> 911
          </a>
          <Link href="/login/hospital" className="whitespace-nowrap rounded-md px-3 py-1.5 font-medium text-slate-600 transition hover:bg-indigo-50 hover:text-indigo-700">
            Hospital<span className="hidden sm:inline"> login</span>
          </Link>
          <Link href="/login/doctor" className="whitespace-nowrap rounded-md bg-linear-to-r from-indigo-600 to-sky-500 px-3 py-1.5 font-medium text-white shadow-sm shadow-indigo-600/25 transition hover:brightness-110">
            Doctor<span className="hidden sm:inline"> login</span>
          </Link>
        </nav>
      </div>
    </header>
  );
}
