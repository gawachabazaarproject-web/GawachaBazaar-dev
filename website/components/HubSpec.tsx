"use client";

import { useEffect, useRef, useState } from "react";
import Image from "next/image";
import { ensureGsap } from "@/lib/gsap";
import RippleButton from "./RippleButton";

const HUBS = [
  {
    name: "Village Collection Point",
    capacity: "2 — 4 TONNES / DAY",
    detail: "Open-air sorting sheds inside the growing block, run by local staff.",
  },
  {
    name: "Nagpur Transit Hub",
    capacity: "12 TONNES / DAY",
    detail: "Cross-dock facility with same-day dispatch — nothing sits overnight.",
  },
];

export default function HubSpec() {
  const sectionRef = useRef<HTMLDivElement>(null);
  const [active, setActive] = useState(0);

  useEffect(() => {
    const { gsap } = ensureGsap();
    const ctx = gsap.context(() => {
      gsap.from(".hub-copy > *", {
        y: 30,
        opacity: 0,
        duration: 0.8,
        stagger: 0.08,
        ease: "power3.out",
        scrollTrigger: { trigger: sectionRef.current, start: "top 65%" },
      });
    }, sectionRef);
    return () => ctx.revert();
  }, []);

  return (
    <section ref={sectionRef} className="relative overflow-hidden bg-primary-900 py-24 sm:py-32">
      <div className="absolute inset-0">
        <Image
          src="/images/bg/hub.jpg"
          alt="Inside a Gawacha Bazaar transit hub"
          fill
          sizes="100vw"
          className="object-cover opacity-40"
        />
        <div className="absolute inset-0 bg-gradient-to-r from-primary-900 via-primary-900/90 to-primary-900/50" />
      </div>

      <div className="relative mx-auto grid max-w-7xl grid-cols-1 items-center gap-16 px-5 sm:px-8 lg:grid-cols-2">
        <div className="hub-copy">
          <p className="eyebrow text-secondary-400">Inside The Network</p>
          <h2 className="mt-4 font-display text-3xl font-bold text-neutral-100 sm:text-5xl">
            Built for a
            <br />
            <span className="font-script italic text-secondary-400">Same-Day</span> Table
          </h2>
          <p className="mt-6 max-w-md text-sm leading-relaxed text-neutral-100/70 sm:text-base">
            No sprawling cold-storage warehouses — just small, fast nodes positioned exactly
            where the produce already is, and exactly where your kitchen needs it.
          </p>
          <RippleButton
            as="a"
            href="#journey"
            rippleColor="rgba(217,165,42,0.4)"
            className="mt-8 inline-flex items-center gap-2 rounded-full bg-secondary-500 px-6 py-3 text-xs font-bold uppercase tracking-widest text-primary-900 transition-transform hover:scale-105"
          >
            See The Full Journey
          </RippleButton>
        </div>

        <div className="rounded-3xl border border-neutral-100/10 bg-primary-800/60 p-8 backdrop-blur-sm sm:p-10">
          <p className="eyebrow text-neutral-100/40">Facility Type</p>
          <p className="mt-2 font-display text-2xl font-semibold text-neutral-100 sm:text-3xl">
            {HUBS[active].name}
          </p>

          <div className="mt-6 border-t border-neutral-100/10 pt-6">
            <p className="eyebrow text-neutral-100/40">Throughput</p>
            <p className="mt-1 font-display text-xl font-semibold text-secondary-400">
              {HUBS[active].capacity}
            </p>
          </div>

          <p className="mt-6 text-sm leading-relaxed text-neutral-100/60">{HUBS[active].detail}</p>

          <div className="mt-8 flex items-center gap-3">
            {HUBS.map((hub, i) => (
              <button
                key={hub.name}
                onClick={() => setActive(i)}
                aria-label={`Show ${hub.name}`}
                className={`h-2 rounded-full transition-all ${
                  i === active ? "w-8 bg-secondary-500" : "w-2 bg-neutral-100/25"
                }`}
              />
            ))}
            <span className="ml-auto eyebrow text-neutral-100/30">
              {active + 1} / {HUBS.length}
            </span>
          </div>
        </div>
      </div>
    </section>
  );
}
