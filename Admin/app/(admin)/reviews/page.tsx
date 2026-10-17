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
        title="Review moderation is coming soon"
        message="Customers cannot leave product reviews yet, so there is nothing to moderate. This page will list reviews for approval once the feature launches."
      />
    </div>
  );
}
