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
        title="Reports are coming soon"
        message="Sales, order-value and top-product reports are not available yet. For today's live numbers, see the Overview page."
      />
    </div>
  );
}
