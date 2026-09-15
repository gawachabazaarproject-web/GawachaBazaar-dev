import React from "react";

export function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center rounded border border-status-danger/20 bg-status-dangerLight px-6 py-12 text-center">
      <p className="font-display text-lg font-semibold text-status-danger">{message}</p>
      <button
        onClick={onRetry}
        className="mt-4 rounded border border-status-danger/40 px-4 py-2 text-sm font-semibold text-status-danger hover:bg-white"
      >
        Retry
      </button>
    </div>
  );
}
