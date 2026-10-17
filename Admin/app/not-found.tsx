import Link from "next/link";

export default function NotFound() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-neutral-100 px-4 text-center">
      <p className="eyebrow text-secondary-600">Error 404</p>
      <h1 className="mt-1 font-display text-2xl font-semibold text-primary-900">This page does not exist</h1>
      <p className="mt-2 max-w-sm text-sm text-neutral-600">The link may be old or mistyped.</p>
      <Link href="/dashboard" className="mt-5 rounded bg-primary-800 px-4 py-2 text-sm font-semibold text-white hover:bg-primary-700">
        Go to Overview
      </Link>
    </div>
  );
}
