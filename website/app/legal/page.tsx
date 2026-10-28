import type { Metadata } from "next";
import Link from "next/link";
import { BUSINESS, POLICIES } from "@/lib/legal";

export const metadata: Metadata = { title: "Policies | Gawacha Bazaar" };

export default function LegalIndex() {
  return (
    <main className="min-h-screen bg-primary-900 px-5 py-16 text-neutral-100/80 sm:px-8">
      <div className="mx-auto max-w-3xl">
        <h1 className="font-display text-4xl font-bold text-neutral-100">Help &amp; Legal Information</h1>
        <ul className="mt-8 divide-y divide-neutral-100/10 border-y border-neutral-100/10">
          {POLICIES.map((p) => (
            <li key={p.slug}>
              <Link href={`/legal/${p.slug}`} className="block py-4 hover:text-secondary-400">
                {p.title}
              </Link>
            </li>
          ))}
        </ul>
        <p className="mt-10 text-sm leading-relaxed">
          {BUSINESS.name} · {BUSINESS.address}
          <br />
          {BUSINESS.phone} · {BUSINESS.email} · FSSAI {BUSINESS.fssai}
        </p>
      </div>
    </main>
  );
}
