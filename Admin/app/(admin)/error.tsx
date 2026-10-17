"use client";

import { useEffect } from "react";
import Link from "next/link";

/** Catches a crash inside any admin page so the sidebar and session survive. */
export default function AdminError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => {
    console.error("Admin page crashed", error);
  }, [error]);

  return (
    <div role="alert" className="mx-auto mt-16 max-w-md rounded border border-status-danger/20 bg-status-dangerLight px-6 py-10 text-center">
      <p className="font-display text-lg font-semibold text-status-danger">Something went wrong on this page</p>
      <p className="mt-2 text-sm text-neutral-700">
        Your work elsewhere is safe. Try again, and if it keeps happening, tell the tech team
        {error.digest ? ` (reference ${error.digest})` : ""}.
      </p>
      <div className="mt-5 flex items-center justify-center gap-3">
        <button onClick={reset} className="rounded bg-primary-800 px-4 py-2 text-sm font-semibold text-white hover:bg-primary-700">
          Try again
        </button>
        <Link href="/dashboard" className="text-sm font-semibold text-primary-700 hover:underline">
          Go to Overview
        </Link>
      </div>
    </div>
  );
}
