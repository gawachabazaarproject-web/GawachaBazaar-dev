"use client";

import { useEffect, useRef } from "react";
import Image from "next/image";
import { ensureGsap } from "@/lib/gsap";
import { IconSprout, IconCheckBadge, IconLeaf } from "./icons";
import ChapterMark from "./ChapterMark";

const REASONS = [
  {
    icon: IconSprout,
    title: "Village Roots",
    desc: "Every grain and vegetable traces directly back to partner growers in local farming communities.",
  },
  {
    icon: IconCheckBadge,
    title: "Hand Graded",
    desc: "Produce is cleaned, sorted, and graded directly at our village hubs to ensure peak quality.",
  },
  {
    icon: IconLeaf,
    title: "Zero Middlemen",
    desc: "Direct grower-to-doorstep pricing means fresher food for you and fairer income for farmers.",
  },
];

export default function VillageCulture() {
  const domeRef = useRef<HTMLDivElement>(null);
  const contentRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const { gsap, ScrollTrigger } = ensureGsap();
    const ctx = gsap.context(() => {
      gsap.fromTo(
        domeRef.current,
        { clipPath: "ellipse(70% 0% at 50% 100%)" },
        {
          clipPath: "ellipse(90% 150% at 50% 100%)",
          ease: "none",
          scrollTrigger: {
            trigger: domeRef.current,
            start: "top bottom",
            end: "bottom 55%",
            scrub: 0.8,
          },
        }
      );

      gsap.utils.toArray<HTMLElement>(".reason-card").forEach((card, i) => {
        gsap.from(card, {
          y: 50,
          opacity: 0,
          duration: 0.8,
          delay: i * 0.1,
          ease: "power3.out",
          scrollTrigger: { trigger: card, start: "top 85%" },
        });
      });
    }, contentRef);
    return () => ctx.revert();
  }, []);

  return (
    <section data-nav-theme="dark" className="relative -mt-36 sm:-mt-56">
      <div
        ref={domeRef}
        className="relative z-10 overflow-hidden bg-primary-800 pb-28 pt-44 sm:pb-40 sm:pt-64"
        style={{ clipPath: "ellipse(70% 0% at 50% 100%)" }}
      >
        <div className="absolute inset-0">
          <Image
            src="/images/bg/village.jpg"
            alt="Rows of vegetables growing in a village farm"
            fill
            sizes="100vw"
            className="object-cover"
          />
          <div className="absolute inset-0 bg-primary-900/90" />
        </div>
        <div ref={contentRef} className="relative mx-auto max-w-6xl px-5 sm:px-8">
          <ChapterMark index={3} tone="light" className="absolute left-1/2 top-4 -translate-x-1/2" />
          <p className="eyebrow relative text-center text-secondary-400">03 / 08 — Three Reasons To Choose Us</p>
          <h2 className="mx-auto mt-4 max-w-4xl text-center font-display text-4xl font-bold uppercase leading-[1.05] text-neutral-100 sm:text-6xl">
            Modern convenience, rooted in village culture.
          </h2>
          <p className="mx-auto mt-8 max-w-2xl text-center text-base leading-relaxed text-neutral-100/70 sm:text-lg">
            Gawacha Bazaar bridges the gap between rural farms and Nagpur&apos;s households.
            We operate sorting nodes directly inside agricultural blocks in Maharashtra —
            connecting customers straight to growers, with fresh, clean food and zero
            middleman delays.
          </p>

          <div className="mt-16 grid grid-cols-1 gap-10 sm:grid-cols-3">
            {REASONS.map((r) => (
              <div key={r.title} className="reason-card border-t border-secondary-500/30 pt-6 text-center sm:text-left">
                <r.icon className="mx-auto h-8 w-8 text-secondary-400 sm:mx-0" />
                <h3 className="mt-4 font-display text-xl font-semibold text-neutral-100">{r.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-neutral-100/60">{r.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
