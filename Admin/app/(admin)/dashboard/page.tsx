import { PageHeader } from "@/components/PageHeader";
import { EmptyState } from "@/components/EmptyState";

/**
 * "What is happening in Gawacha Bazaar right now?" - per the admin-panel
 * spec, this page must never show a number the backend can't actually
 * compute. Today, that's every number on this page: there is no
 * admin-wide order list/metrics endpoint yet (see the Phase 1 audit), so
 * every panel below is an honest "not wired up yet" state rather than a
 * fabricated KPI. This gets replaced panel-by-panel as each backend
 * endpoint is built (Orders in Phase 5, Inventory alerts already have a
 * real endpoint and come next, etc.) - never all at once, never with fake
 * data standing in for what's missing.
 */
export default function DashboardPage() {
  return (
    <div>
      <PageHeader
        eyebrow="Overview"
        title="Today at Gawacha Bazaar"
        description="A live snapshot of orders, inventory, and operations requiring attention."
      />

      <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        {["Orders", "Revenue", "Pending", "Out for delivery", "Delivered", "Cancelled"].map((label) => (
          <div key={label} className="rounded border border-neutral-200 bg-white p-4">
            <p className="text-xs font-medium uppercase tracking-wide text-neutral-500">{label}</p>
            <p className="mt-2 font-display text-2xl text-neutral-300">—</p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <EmptyState
          icon="package"
          title="Orders requiring attention"
          message="Needs an admin-wide order list endpoint (Phase 5) - today the backend only supports cancelling one order by id."
        />
        <EmptyState
          icon="box"
          title="Low stock"
          message="The inventory endpoints already support this (GET /inventory/lots) - wiring this panel up is next."
        />
        <EmptyState
          icon="star"
          title="Pending reviews"
          message="No review domain exists in the backend yet - there is nothing to moderate until that module is built."
        />
        <EmptyState
          icon="truck"
          title="Delivery issues"
          message="Needs an aggregate delivery-status view on top of the existing fulfillments endpoints."
        />
      </div>
    </div>
  );
}
