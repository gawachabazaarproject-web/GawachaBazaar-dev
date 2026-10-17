import { PageHeader } from "@/components/PageHeader";
import { EmptyState } from "@/components/EmptyState";

export default function AuditLogPage() {
  return (
    <div>
      <PageHeader
        eyebrow="Compliance"
        title="Audit Log"
        description="Who changed what, when - across every admin action that changes business state."
      />
      <EmptyState
        icon="shield"
        title="Audit log viewer is coming soon"
        message="Every admin change is already recorded for compliance, but there is no screen to browse the history yet. Product and category pages show their own activity feeds in the meantime."
      />
    </div>
  );
}
