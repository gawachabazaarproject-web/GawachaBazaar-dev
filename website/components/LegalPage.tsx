import Link from "next/link";
import type { Policy } from "@/lib/legal";

export default function LegalPage({ policy }: { policy: Policy }) {
  return (
    <main className="min-h-screen bg-primary-900 px-5 py-16 text-neutral-100/80 sm:px-8">
      <article className="mx-auto max-w-3xl">
        <Link href="/legal" className="text-sm text-secondary-400 hover:underline">
          ← All policies
        </Link>
        <h1 className="mt-6 font-display text-4xl font-bold text-neutral-100">{policy.title}</h1>
        {policy.intro ? <p className="mt-6 leading-relaxed">{policy.intro}</p> : null}
        {policy.sections.map((s, i) => (
          <section key={i} className="mt-8">
            {s.heading ? <h2 className="text-lg font-semibold text-secondary-400">{s.heading}</h2> : null}
            {s.paragraphs?.map((p, j) => (
              <p key={j} className="mt-3 leading-relaxed">
                {p}
              </p>
            ))}
            {s.bullets ? (
              <ul className="mt-3 list-disc space-y-2 pl-6 leading-relaxed">
                {s.bullets.map((b, j) => (
                  <li key={j}>{b}</li>
                ))}
              </ul>
            ) : null}
          </section>
        ))}
        <p className="mt-12 text-xs text-neutral-100/40">© 2026 GAWACHA BAAZAAR. All Rights Reserved.</p>
      </article>
    </main>
  );
}
