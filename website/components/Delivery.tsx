"use client";

import { useEffect, useRef } from "react";
import { ensureGsap } from "@/lib/gsap";
import { IconCheck, IconBike } from "./icons";
import EditorialLink from "./EditorialLink";
import ChapterMark from "./ChapterMark";

const POINTS = [
  "No multi-day cold storage holds",
  "Eco-friendly breathable packaging",
  "Trained, contact-free local riders",
  "Serving all major Nagpur sectors daily",
];

export default function Delivery() {
  const sectionRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const { gsap } = ensureGsap();
    const ctx = gsap.context(() => {
      gsap.from(".deliver-copy > *", {
        y: 30,
        opacity: 0,
        duration: 0.8,
        stagger: 0.08,
        ease: "power3.out",
        scrollTrigger: { trigger: sectionRef.current, start: "top 65%" },
      });
      gsap.from(".deliver-card", {
        y: 40,
        opacity: 0,
        scale: 0.96,
        duration: 0.9,
        ease: "power3.out",
        scrollTrigger: { trigger: sectionRef.current, start: "top 55%" },
      });
    }, sectionRef);
    return () => ctx.revert();
  }, []);

  return (
    <section
      id="delivery"
      ref={sectionRef}
      className="relative bg-primary-800 pb-24 pt-28 sm:pb-32 sm:pt-36"
      style={{ clipPath: "polygon(0 4vw, 100% 0, 100% 100%, 0 100%)" }}
    >
      <ChapterMark index={6} tone="light" className="absolute left-4 top-10 sm:left-8" />
      <div className="relative mx-auto grid max-w-7xl grid-cols-1 items-center gap-16 px-5 sm:px-8 lg:grid-cols-2">
        <div className="deliver-copy">
          <p className="eyebrow text-secondary-400">06 / 08 — Direct Delivery Logistics</p>
          <h2 className="mt-4 font-display text-3xl font-bold leading-tight text-neutral-100 sm:text-5xl">
            From our bazaar to your doorstep.
          </h2>
          <p className="mt-6 max-w-lg text-base leading-relaxed text-neutral-100/70 sm:text-lg">
            We skip typical wholesale cold warehouses. Vegetables sorted at dawn in our
            village nodes are loaded straight into breathable, insulated cargo boxes and
            dispatched to Nagpur city the same day.
          </p>

          <div className="mt-8 grid grid-cols-1 gap-x-8 gap-y-4 sm:grid-cols-2">
            {POINTS.map((point) => (
              <div key={point} className="flex items-start gap-3">
                <IconCheck className="mt-0.5 h-5 w-5 shrink-0 text-secondary-400" />
                <span className="text-sm text-neutral-100/80">{point}</span>
              </div>
            ))}
          </div>

          <EditorialLink as="a" href="#delivery" tone="light" className="mt-10">
            View Delivery Timelines
          </EditorialLink>
        </div>

        <div className="deliver-card relative rounded-none border border-secondary-500/20 bg-primary-700/50 p-10 text-center">
          <div className="mx-auto flex h-20 w-20 items-center justify-center rounded-full bg-secondary-500/20">
            <IconBike className="h-10 w-10 text-secondary-400" />
          </div>
          <h3 className="mt-6 font-display text-xl font-semibold text-neutral-100">
            Nagpur Neighborhood Dispatch
          </h3>
          <p className="mt-3 text-sm leading-relaxed text-neutral-100/60">
            Our riders travel across Nagpur neighborhoods, bringing fresh, zero-storage
            produce straight to your gates — from Dharampeth to Wardhaman Nagar, Manish
            Nagar to Katol Road.
          </p>
        </div>
      </div>
    </section>
  );
}
