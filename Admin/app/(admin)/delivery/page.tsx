import { PageHeader } from "@/components/PageHeader";
import { EmptyState } from "@/components/EmptyState";

export default function DeliveryPage() {
  return (
    <div>
      <PageHeader
        eyebrow="Operations"
        title="Delivery"
        description="Active deliveries, partner assignments, and fulfillment status."
      />
      <EmptyState
        icon="truck"
        title="Backend is ready - this screen is next"
        message="fulfillments.py already supports listing/filtering, status advancement, and delivery-partner assignment. There's no dedicated delivery-partner profile (a partner is just a User with the DELIVERY_PARTNER role) - Phase 17 covers whether that needs to change. Phase 16 wires this operations view up first."
      />
    </div>
  );
}
