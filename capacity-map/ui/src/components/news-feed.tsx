import type { CSSProperties } from "react";
import { formatTime, miles } from "../geo";
import type { Hospital, Incident, WeatherAlert } from "../types";
import "../effects.css";

interface NewsItem {
  id: string;
  tag: string;
  tone: "red" | "amber" | "blue";
  title: string;
  body: string;
  source: string;
  time: string | null;
}

const TONES = {
  red: { pill: "bg-red-50 text-red-700 ring-red-600/20", bar: "border-l-red-500" },
  amber: { pill: "bg-amber-50 text-amber-800 ring-amber-600/25", bar: "border-l-amber-400" },
  blue: { pill: "bg-sky-50 text-sky-700 ring-sky-600/20", bar: "border-l-sky-500" },
};

function weatherTone(severity: string): NewsItem["tone"] {
  if (severity === "Extreme" || severity === "Severe") return "red";
  if (severity === "Moderate") return "amber";
  return "blue";
}

/** Incidents first, then full hospitals (each with the nearest open alternative), then weather. */
export function buildNews(hospitals: Hospital[], incidents: Incident[], alerts: WeatherAlert[], generatedAt: string): NewsItem[] {
  const items: NewsItem[] = incidents.map((i) => ({
    id: i.id,
    tag: "Incident",
    tone: "red",
    title: i.title,
    body: `${i.summary} Expect heavy ambulance traffic and long waits at these emergency departments.`,
    source: "EmerFlow",
    time: i.started,
  }));

  const open = hospitals.filter((h) => h.status === "open");
  for (const h of hospitals.filter((x) => x.status === "critical")) {
    const alt = open.map((a) => ({ a, d: miles([h.lat, h.lon], [a.lat, a.lon]) })).sort((x, y) => x.d - y.d)[0];
    const waiting = h.er.waiting > 0 ? `${h.er.waiting} patients are waiting for an ER bay. ` : "The ER has almost no open bays. ";
    items.push({
      id: `full-${h.id}`,
      tag: "Hospital capacity",
      tone: "amber",
      title: `${h.name} emergency department is full`,
      body:
        waiting +
        (alt ? `For non-life-threatening care, ${alt.a.name} (${alt.d.toFixed(1)} mi away) is accepting patients.` : "Nearby hospitals are also busy."),
      source: "EmerFlow",
      time: generatedAt,
    });
  }

  for (const a of alerts) {
    items.push({ id: a.id, tag: a.event, tone: weatherTone(a.severity), title: a.headline, body: a.area, source: "NWS", time: a.effective });
  }
  return items;
}

export function NewsFeed({
  hospitals,
  incidents,
  alerts,
  alertsAvailable,
  generatedAt,
  className = "",
}: {
  hospitals: Hospital[];
  incidents: Incident[];
  alerts: WeatherAlert[];
  /** null while weather alerts are loading. */
  alertsAvailable: boolean | null;
  generatedAt: string;
  className?: string;
}) {
  const news = buildNews(hospitals, incidents, alerts, generatedAt);
  return (
    <ul className={`divide-y divide-slate-100 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm ${className}`}>
      {news.map((n, i) => (
        <li
          key={n.id}
          style={{ "--emf-delay": `${i * 80}ms` } as CSSProperties}
          className={`emf-rise grid gap-x-6 gap-y-1.5 border-l-4 px-5 py-4 transition-colors hover:bg-slate-50 sm:grid-cols-[150px_minmax(0,1fr)_auto] ${TONES[n.tone].bar}`}
        >
          <p>
            <span className={`inline-block rounded-full px-2 py-0.5 text-[11px] font-semibold ring-1 ring-inset ${TONES[n.tone].pill}`}>{n.tag}</span>
          </p>
          <div>
            <h3 className="text-sm font-medium text-slate-900">{n.title}</h3>
            <p className="mt-0.5 text-[13px] leading-relaxed text-slate-500">{n.body}</p>
          </div>
          <p className="text-xs text-slate-400 sm:text-right">
            {n.source}
            {n.time && <span className="tabular-nums"> · {formatTime(n.time)}</span>}
          </p>
        </li>
      ))}
      {alertsAvailable !== null && alerts.length === 0 && (
        <li className="px-5 py-4 text-[13px] text-slate-400">
          {alertsAvailable ? "No active weather alerts for your area." : "Weather alerts are unavailable right now."}
        </li>
      )}
    </ul>
  );
}
