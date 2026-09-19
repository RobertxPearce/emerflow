// Public API of @hospital-swarm/capacity-map. Anything not exported here is internal.

// Everything in one component
export { CapacityDashboard } from "./components/capacity-dashboard";
export type { CapacityDashboardProps } from "./components/capacity-dashboard";

// Pieces
export { CapacityMap } from "./components/capacity-map";
export type { CapacityMapProps } from "./components/capacity-map";
export { HospitalList } from "./components/hospital-list";
export { StatusLegend } from "./components/status-legend";
export { RegionStats } from "./components/region-stats";
export type { StatPick } from "./components/region-stats";
export { LiveTicker } from "./components/live-ticker";
export { NewsFeed, buildNews } from "./components/news-feed";
export { SimulationPanel, SimulationTimeline, SimulationVerdict } from "./components/simulation-panel";

// State
export { useRegion } from "./use-region";
export type { RegionState } from "./use-region";
export { useSimulation } from "./use-simulation";
export type { SimulationState, SimulationPhase } from "./use-simulation";
export { useLocation } from "./use-location";
export type { LocationState } from "./use-location";
export { useWeatherAlerts } from "./use-weather-alerts";
export { useCountUp } from "./use-count-up";

// Data sources
export { swarmSource, recordedSource, withFallback, sampleRegion, sampleSimulation } from "./sources";
export type { RegionSource, SimulateParams } from "./sources";

// Helpers
export { STATUS, STATUSES, rankHospitals, miles, driveMinutes, formatWait, formatTime, directionsUrl, countByStatus } from "./geo";
export type { RankedHospital } from "./geo";

// Data shapes
export type {
  Audience,
  Hospital,
  Incident,
  LatLon,
  RegionSnapshot,
  Simulation,
  SimulationFrame,
  SimulationOutcome,
  SortBy,
  Status,
  UnitLoad,
  WeatherAlert,
} from "./types";
