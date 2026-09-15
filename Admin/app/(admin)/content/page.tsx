import { PageHeader } from "@/components/PageHeader";
import { EmptyState } from "@/components/EmptyState";

export default function ContentPage() {
  return (
    <div>
      <PageHeader
        eyebrow="Marketing"
        title="Content"
        description="Homepage slides, featured collections, and editorial sections shown to customers."
      />
      <EmptyState
        icon="file-text"
        title="No content domain exists yet"
        message="Homepage/carousel content is currently hardcoded in the mobile and website apps, not backend-driven. Phase 20 turns it into a real content domain (same backend work as Promotions) so this panel becomes the actual source of truth."
      />
    </div>
  );
}
