import { PageHeader } from "@/components/PageHeader";
import { EmptyState } from "@/components/EmptyState";

export default function ReportsPage() {
  return (
    <div>
      <PageHeader
        eyebrow="Analytics"
        title="Reports"
        description="Sales, product, inventory, and delivery performance, computed from real order data."
      />
      <EmptyState
        icon="bar-chart"
        title="Waiting on the admin order list (Phase 5)"
        message="Every report here (sales, AOV, cancellation rate, top products) is an aggregation over orders the admin panel can't query yet. Phase 19 builds these once that endpoint exists - no metric will be shown until the backend can actually compute it."
      />
    </div>
  );
}
