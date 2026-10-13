import React from "react";

/** Small inline spinner for buttons - inherits the button's text colour. */
export function Spinner({ className = "" }: { className?: string }) {
  return (
    <svg
      className={`h-4 w-4 animate-spin ${className}`}
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
    >
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="3" opacity="0.25" />
      <path d="M21 12a9 9 0 0 0-9-9" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
    </svg>
  );
}

/** Button content while an action is in flight: spinner + label. */
export function BusyLabel({ children }: { children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center justify-center gap-2">
      <Spinner />
      {children}
    </span>
  );
}

/** Branded loader for a page, section or the whole screen. */
export function PageLoader({
  label = "Loading...",
  fullScreen = false,
}: {
  label?: string;
  fullScreen?: boolean;
}) {
  return (
    <div
      role="status"
      aria-live="polite"
      className={`flex flex-col items-center justify-center gap-4 ${fullScreen ? "min-h-screen bg-neutral-100" : "py-24"}`}
    >
      <div className="relative h-14 w-14">
        <span className="absolute inset-0 animate-ping rounded-full bg-primary-200 opacity-60" />
        <span className="absolute inset-0 rounded-full border-4 border-primary-100" />
        <span className="absolute inset-0 animate-spin rounded-full border-4 border-transparent border-t-primary-700" />
      </div>
      <div className="flex items-center gap-1.5" aria-hidden="true">
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className="h-2 w-2 animate-bounce rounded-full bg-secondary-500"
            style={{ animationDelay: `${i * 140}ms` }}
          />
        ))}
      </div>
      <p className="eyebrow text-neutral-500">{label}</p>
    </div>
  );
}
