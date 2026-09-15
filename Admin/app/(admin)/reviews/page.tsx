import { PageHeader } from "@/components/PageHeader";
import { EmptyState } from "@/components/EmptyState";

export default function ReviewsPage() {
  return (
    <div>
      <PageHeader
        eyebrow="Quality"
        title="Reviews"
        description="Moderate product reviews and surface rating trends."
      />
      <EmptyState
        icon="star"
        title="No review domain exists yet"
        message="Confirmed by the Phase 1 audit: there is no Review model, table, or endpoint anywhere in the backend. Phase 14 adds the domain (rating, text, moderation status, order-verification link) before this screen can show anything real."
      />
    </div>
  );
}
