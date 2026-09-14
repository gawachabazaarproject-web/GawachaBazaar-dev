"use client";

import { useEffect, useRef } from "react";
import Image from "next/image";
import { ensureGsap } from "@/lib/gsap";
import EditorialLink from "./EditorialLink";

const ZONES = [
  { name: "Katol Road Belt", dist: "35 KM" },
  { name: "Wardha Road Villages", dist: "40 KM" },
  { name: "Kalmeshwar Farms", dist: "28 KM" },
  { name: "Nagpur City Hub", dist: "0 KM" },
];

export default function AerialLocation() {
  const sectionRef = useRef<HTMLDivElement>(null);
  const imgRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const { gsap } = ensureGsap();
    const ctx = gsap.context(() => {
      gsap.fromTo(
        imgRef.current,
        { scale: 1.15, yPercent: -6 },
        {
          scale: 1,
          yPercent: 6,
          ease: "none",
          scrollTrigger: { trigger: sectionRef.current, start: "top bottom", end: "bottom top", scrub: 0.6 },
        }
      );
      gsap.from(".aerial-copy > *", {
        y: 30,
        opacity: 0,
        duration: 0.8,
        stagger: 0.1,
        ease: "power3.out",
        scrollTrigger: { trigger: sectionRef.current, start: "top 60%" },
      });
      gsap.utils.toArray<HTMLElement>(".zone-chip").forEach((chip, i) => {
        gsap.from(chip, {
          x: -20,
          opacity: 0,
          duration: 0.6,
          delay: i * 0.08,
          ease: "power2.out",
          scrollTrigger: { trigger: chip, start: "top 90%" },
        });
      });
    }, sectionRef);
    return () => ctx.revert();
  }, []);

  return (
    <section ref={sectionRef} className="relative min-h-[90vh] overflow-hidden bg-primary-900 sm:min-h-[640px]">
      <div ref={imgRef} className="absolute inset-0">
        <Image
          src="/images/bg/aerial.jpg"
          alt="Aerial view of Maharashtra farmland at sunrise"
          fill
          sizes="100vw"
          className="object-cover"
        />
      </div>
      <div className="absolute inset-0 bg-gradient-to-t from-primary-900 via-primary-900/40 to-primary-900/10" />
      <div className="absolute inset-0 bg-gradient-to-r from-primary-900/90 via-primary-900/10 to-transparent" />

      <div className="relative z-10 mx-auto flex min-h-full max-w-7xl flex-col justify-between gap-16 px-5 py-16 sm:px-8 sm:py-20">
        <div className="aerial-copy max-w-xl">
          <p className="eyebrow text-secondary-400">Maharashtra&apos;s Fresh Belt</p>
          <h2 className="mt-4 font-display text-4xl font-bold uppercase leading-[0.95] text-neutral-100 sm:text-6xl">
            The route to
            <br />
            your table
          </h2>
          <p className="mt-6 max-w-md text-sm leading-relaxed text-neutral-100/75 sm:text-base">
            Every village node sits within a couple of hours of Nagpur — close enough that
            what&apos;s picked at dawn reaches your kitchen the same evening.
          </p>
          <EditorialLink as="a" href="#delivery" tone="light" className="mt-9">
            View Delivery Zones
          </EditorialLink>
        </div>

        <div className="flex flex-wrap gap-x-10 gap-y-4">
          {ZONES.map((zone) => (
            <div key={zone.name} className="zone-chip">
              <p className="font-display text-base font-semibold text-neutral-100 sm:text-lg">{zone.dist}</p>
              <p className="eyebrow mt-1 text-neutral-100/50">{zone.name}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
