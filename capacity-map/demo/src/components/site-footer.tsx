export function SiteFooter() {
  return (
    <footer className="mt-16 bg-linear-to-br from-indigo-950 via-slate-900 to-sky-950">
      <div className="mx-auto flex max-w-7xl flex-col gap-2 px-4 py-8 text-xs text-slate-400 sm:flex-row sm:justify-between sm:px-6">
        <p>
          EmerFlow · HopHacks 2026. Hospital capacity shown here is <span className="font-medium text-sky-300">simulated</span> for
          demonstration and does not reflect real hospital conditions.
        </p>
        <p>Map © Esri, OpenStreetMap contributors · Weather alerts: National Weather Service</p>
      </div>
    </footer>
  );
}
