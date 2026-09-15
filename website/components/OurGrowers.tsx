"use client";

import { useEffect, useRef } from "react";
import Image from "next/image";
import { ensureGsap } from "@/lib/gsap";
import EditorialLink from "./EditorialLink";
import ChapterMark from "./ChapterMark";

export default function OurGrowers() {
  const sectionRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const { gsap } = ensureGsap();
    const ctx = gsap.context(() => {
      gsap.from(".grower-copy > *", {
        y: 30,
        opacity: 0,
        duration: 0.8,
        stagger: 0.1,
        ease: "power3.out",
        scrollTrigger: { trigger: sectionRef.current, start: "top 65%" },
      });
      gsap.fromTo(
        ".grower-photo",
        { scale: 1.15 },
        {
          scale: 1,
          ease: "none",
          scrollTrigger: { trigger: sectionRef.current, start: "top bottom", end: "bottom top", scrub: 0.6 },
        }
      );
    }, sectionRef);
    return () => ctx.revert();
  }, []);

  return (
    <section ref={sectionRef} data-nav-theme="light" className="relative overflow-hidden bg-neutral-100 py-24 sm:py-32">
      <ChapterMark index={7} className="absolute left-0 top-2 sm:top-4" />
      <div className="relative mx-auto grid max-w-7xl grid-cols-1 items-center gap-14 px-5 sm:px-8 lg:grid-cols-2">
        <div className="grower-copy order-2 lg:order-1">
          <p className="eyebrow text-primary-600">07 / 08 — Grown By Real People</p>
          <h2 className="mt-4 font-display text-3xl font-bold leading-tight text-primary-800 sm:text-5xl">
            Every crate has a name behind it.
          </h2>
          <p className="mt-6 max-w-md text-sm leading-relaxed text-primary-700/70 sm:text-base">
            We don&apos;t buy from anonymous mandis. Every partner farm is visited, verified,
            and paid directly — so the person who grew your dinner actually sees the money
            you spent on it.
          </p>
          <div className="mt-8 border-t border-primary-800/10 pt-6">
            <p className="font-display text-xl font-semibold text-primary-800">Ravindra Kale</p>
            <p className="eyebrow mt-1 text-primary-600">Onion &amp; Root Vegetable Grower · Katol Road</p>
            <p className="mt-3 max-w-sm text-sm italic leading-relaxed text-primary-700/60">
              &ldquo;Gawacha Bazaar picks up at the farm gate. No broker, no waiting three days
              to get paid.&rdquo;
            </p>
          </div>
          <EditorialLink as="a" href="#contact" tone="dark" className="mt-9">
            Meet Our Growers
          </EditorialLink>
        </div>

        <div className="order-1 aspect-[4/5] overflow-hidden rounded-none lg:order-2">
          <div className="grower-photo relative h-full w-full">
            <Image
              src="/images/people/grower.jpg"
              alt="Ravindra Kale, a partner vegetable grower"
              fill
              sizes="(min-width: 1024px) 480px, 100vw"
              className="object-cover"
            />
          </div>
        </div>
      </div>
    </section>
  );
}
