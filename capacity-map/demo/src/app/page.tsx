import { CapacityDashboard } from "@hospital-swarm/capacity-map";
import { SiteFooter } from "@/components/site-footer";
import { SiteHeader } from "@/components/site-header";

export default function Home() {
  return (
    <>
      <SiteHeader />
      <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 sm:py-10">
        <CapacityDashboard />
      </main>
      <SiteFooter />
    </>
  );
}
