import { PageHeader } from "@/components/PageHeader";
import { EmptyState } from "@/components/EmptyState";

export default function SettingsPage() {
  return (
    <div>
      <PageHeader eyebrow="Platform" title="Settings" description="Store, delivery, and platform configuration." />
      <EmptyState
        icon="settings"
        title="No DB-backed settings domain exists yet"
        message="Today's 'Settings' is only environment-driven app configuration (app/core/config.py) - not something an admin can view or edit. Phase 23 defines what's genuinely safe to expose here (never secrets/API keys) before building it."
      />
    </div>
  );
}
