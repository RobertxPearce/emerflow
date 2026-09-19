"use client";

import { useState } from "react";

// Staff sign-in isn't connected to an identity provider yet; the form only shows that.
export function LoginForm({ idLabel }: { idLabel: string }) {
  const [submitted, setSubmitted] = useState(false);
  const input =
    "mt-1.5 block w-full rounded-lg border-0 px-3 py-2 text-sm text-slate-900 shadow-sm ring-1 ring-inset ring-slate-300 placeholder:text-slate-400 focus:ring-2 focus:ring-inset focus:ring-indigo-500 focus:outline-none";

  return (
    <form
      className="mt-6 space-y-4"
      onSubmit={(e) => {
        e.preventDefault();
        setSubmitted(true);
      }}
    >
      <label className="block text-sm font-medium text-slate-700">
        {idLabel}
        <input type="email" name="email" autoComplete="username" required className={input} placeholder="name@hospital.org" />
      </label>
      <label className="block text-sm font-medium text-slate-700">
        Password
        <input type="password" name="password" autoComplete="current-password" required className={input} />
      </label>
      <button
        type="submit"
        className="w-full rounded-lg bg-linear-to-r from-indigo-600 to-sky-500 px-3 py-2.5 text-sm font-semibold text-white shadow-md shadow-indigo-600/25 transition hover:brightness-110"
      >
        Sign in
      </button>
      {submitted && (
        <p role="status" className="rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800 ring-1 ring-inset ring-amber-600/20">
          Staff sign-in isn&apos;t connected yet in this demo.
        </p>
      )}
    </form>
  );
}
