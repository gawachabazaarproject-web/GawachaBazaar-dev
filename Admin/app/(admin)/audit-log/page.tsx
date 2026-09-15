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
        title="No general-purpose audit log exists yet"
        message="The closest thing today is StockMovement (inventory-only) and per-domain audit columns on Order/Refund (cancelled_by, approved_by, etc.). Phase 22 adds a unified audit-log domain so every admin mutation is traceable in one place, not scattered per table."
      />
    </div>
  );
}
