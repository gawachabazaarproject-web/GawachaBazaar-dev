import React from "react";

export function TableSkeleton({ rows = 8, columns = 8 }: { rows?: number; columns?: number }) {
  return (
    <div className="animate-pulse divide-y divide-neutral-100">
      {Array.from({ length: rows }).map((_, r) => (
        <div key={r} className="flex items-center gap-4 px-4 py-3">
          {Array.from({ length: columns }).map((__, c) => (
            <div key={c} className="h-3 flex-1 rounded bg-neutral-200" />
          ))}
        </div>
      ))}
    </div>
  );
}
