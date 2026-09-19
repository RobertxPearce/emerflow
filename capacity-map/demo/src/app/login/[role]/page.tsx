import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Logo } from "@/components/logo";
import { LoginForm } from "./login-form";

const ROLES = {
  hospital: {
    title: "Hospital sign in",
    blurb: "Manage your facility's capacity, coordinate transfers and respond to regional incidents.",
    idLabel: "Facility email",
    other: { href: "/login/doctor", label: "Signing in as a doctor?" },
  },
  doctor: {
    title: "Doctor sign in",
    blurb: "Review patient transfers, flagged records and your unit's live bed plan.",
    idLabel: "Work email",
    other: { href: "/login/hospital", label: "Signing in for a hospital?" },
  },
} as const;

export function generateStaticParams() {
  return Object.keys(ROLES).map((role) => ({ role }));
}

export async function generateMetadata({ params }: PageProps<"/login/[role]">): Promise<Metadata> {
  const { role } = await params;
  return { title: `${ROLES[role as keyof typeof ROLES]?.title ?? "Sign in"} · EmerFlow` };
}

export default async function LoginPage({ params }: PageProps<"/login/[role]">) {
  const { role } = await params;
  const r = ROLES[role as keyof typeof ROLES];
  if (!r) notFound();

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-linear-to-br from-indigo-50 via-white to-sky-50 px-4 py-12">
      <Logo />
      <div className="mt-8 w-full max-w-sm rounded-2xl border border-indigo-100 bg-white p-7 shadow-xl shadow-indigo-900/5">
        <h1 className="text-xl font-semibold tracking-tight text-slate-900">{r.title}</h1>
        <p className="mt-1.5 text-sm leading-relaxed text-slate-500">{r.blurb}</p>
        <LoginForm idLabel={r.idLabel} />
      </div>
      <div className="mt-6 flex gap-4 text-sm">
        <Link href={r.other.href} className="font-medium text-slate-600 hover:text-slate-900">
          {r.other.label}
        </Link>
        <span className="text-slate-300">|</span>
        <Link href="/" className="font-medium text-slate-600 hover:text-slate-900">
          ← Back to public map
        </Link>
      </div>
    </div>
  );
}
