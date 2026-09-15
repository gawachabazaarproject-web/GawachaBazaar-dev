import { PageHeader } from "@/components/PageHeader";
import { EmptyState } from "@/components/EmptyState";

export default function PaymentsPage() {
  return (
    <div>
      <PageHeader
        eyebrow="Finance"
        title="Payments & Refunds"
        description="Review payment status and manage the refund approval workflow."
      />
      <EmptyState
        icon="credit-card"
        title="Refunds are ready; payments list is not"
        message="payments.py's admin_router already supports list/approve/reject/process for refunds (ADMIN-only by design). There's no admin endpoint to list Payment records directly yet - only refund-linked payments are reachable today. Phase 18 wires refunds up first, then adds the payments list."
      />
    </div>
  );
}
