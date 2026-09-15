import React from "react";
import { formatStatusLabel, statusTone } from "@/lib/status-tone";

const TONE_CLASSES: Record<string, string> = {
  success: "bg-status-successLight text-status-success",
  warning: "bg-status-warningLight text-status-warning",
  danger: "bg-status-dangerLight text-status-danger",
  info: "bg-status-infoLight text-status-info",
  neutral: "bg-neutral-200 text-neutral-600",
};

export function StatusBadge({ status, label }: { status: string; label?: string }) {
  const tone = statusTone(status);
  return (
    <span
      className={`inline-flex items-center rounded px-2 py-0.5 text-xs font-semibold ${TONE_CLASSES[tone]}`}
    >
      {label ?? formatStatusLabel(status)}
    </span>
  );
}
