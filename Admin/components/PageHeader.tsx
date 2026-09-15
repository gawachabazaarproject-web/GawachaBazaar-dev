import React from "react";

export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow: string;
  title: string;
  description?: string;
  actions?: React.ReactNode;
}) {
  return (
    <div className="mb-6 flex items-start justify-between gap-4">
      <div>
        <p className="eyebrow text-secondary-600">{eyebrow}</p>
        <h1 className="mt-1 font-display text-2xl font-semibold text-primary-900">{title}</h1>
        {description && <p className="mt-1 max-w-xl text-sm text-neutral-600">{description}</p>}
      </div>
      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </div>
  );
}
