import type { Metadata } from "next";
import { notFound } from "next/navigation";
import LegalPage from "@/components/LegalPage";
import { POLICIES, getPolicy } from "@/lib/legal";

type Props = { params: Promise<{ slug: string }> };

export function generateStaticParams() {
  return POLICIES.map((p) => ({ slug: p.slug }));
}

export const dynamicParams = false;

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const policy = getPolicy((await params).slug);
  return { title: policy ? `${policy.title} | Gawacha Bazaar` : "Gawacha Bazaar" };
}

export default async function Page({ params }: Props) {
  const policy = getPolicy((await params).slug);
  if (!policy) notFound();
  return <LegalPage policy={policy} />;
}
