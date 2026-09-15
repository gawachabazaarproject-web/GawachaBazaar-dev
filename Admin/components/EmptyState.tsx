import React from "react";
import { Icon, IconName } from "./icons";

/**
 * Used both for genuinely-empty operational lists ("no pending reviews")
 * and for modules this admin panel hasn't built yet ("Phase 14"). Never
 * fills the gap with placeholder/fake data - see the admin build rule
 * that real data only ever comes from the backend.
 */
export function EmptyState({
  icon = "box",
  title,
  message,
  action,
}: {
  icon?: IconName;
  title: string;
  message: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded border border-dashed border-neutral-300 bg-white px-6 py-16 text-center">
      <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-neutral-100 text-neutral-400">
        <Icon name={icon} size={22} />
      </div>
      <p className="font-display text-lg font-semibold text-primary-900">{title}</p>
      <p className="mt-1 max-w-sm text-sm text-neutral-500">{message}</p>
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
