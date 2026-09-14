"use client";

import { useEffect, useRef } from "react";
import Image from "next/image";
import { ensureGsap } from "@/lib/gsap";
import ChapterMark from "./ChapterMark";

const SEASONS = [
  {
    tag: "Winter's Pick",
    items: "Carrots & Greens",
    desc: "Sweeter roots and tender leaves — the soil turns cool, the flavour turns up.",
    img: "/images/bg/carrots.jpg",
  },
  {
    tag: "Summer's Pick",
    items: "Mango & Watermelon",
    desc: "The season Nagpur waits all year for. We move it fast, before the heat does.",
    img: "/images/gallery/mango.jpg",
  },
  {
    tag: "Monsoon's Pick",
    items: "Citrus & Berries",
    desc: "Bright, sharp, and quick to spoil elsewhere — which is exactly why we don't wait.",
    img: "/images/gallery/orange.jpg",
  },
];

export default function SeasonBoard() {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const { gsap } = ensureGsap();
    const ctx = gsap.context(() => {
      gsap.utils.toArray<HTMLElement>(".season-card").forEach((card, i) => {
        gsap.from(card, {
          y: 50,
          opacity: 0,
          duration: 0.8,
          delay: i * 0.1,
          ease: "power3.out",
          scrollTrigger: { trigger: card, start: "top 85%" },
        });
      });
    }, ref);
    return () => ctx.revert();
  }, []);

  return (
    <section ref={ref} className="relative overflow-hidden bg-primary-800 py-24 sm:py-32">
      <ChapterMark index={5} tone="light" className="absolute left-0 top-2 sm:top-4" />
      <div className="relative mx-auto max-w-7xl px-5 sm:px-8">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="eyebrow text-secondary-400">05 / 08 — A Village Calendar</p>
            <h2 className="mt-3 max-w-xl font-display text-3xl font-bold text-neutral-100 sm:text-5xl">
              What&apos;s good, right now.
            </h2>
          </div>
          <p className="max-w-sm text-sm leading-relaxed text-neutral-100/60">
            Our catalog shifts with the harvest — not the other way around. Here&apos;s what
            that has meant, season after season.
          </p>
        </div>

        <div className="mt-14 grid grid-cols-1 gap-6 sm:grid-cols-3">
          {SEASONS.map((s) => (
            <div key={s.tag} className="season-card group relative aspect-[3/4] overflow-hidden rounded-none">
              <Image
                src={s.img}
                alt={s.items}
                fill
                sizes="(min-width: 640px) 33vw, 100vw"
                className="object-cover transition-transform duration-700 group-hover:scale-110"
              />
              <div className="absolute inset-0 bg-gradient-to-t from-primary-900/90 via-primary-900/30 to-primary-900/10" />
              <div className="absolute inset-0 flex flex-col justify-end p-7">
                <p className="eyebrow text-secondary-400">{s.tag}</p>
                <h3 className="mt-2 font-display text-2xl font-bold text-neutral-100">{s.items}</h3>
                <p className="mt-3 text-sm leading-relaxed text-neutral-100/70">{s.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
