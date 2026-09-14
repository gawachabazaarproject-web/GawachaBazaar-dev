"use client";

import { useEffect, useRef, useState } from "react";
import Image from "next/image";
import { ensureGsap } from "@/lib/gsap";
import RippleButton from "./RippleButton";

const HOTSPOTS = [
  { top: "34%", left: "62%", label: "Harvested at dawn, daily" },
  { top: "64%", left: "80%", label: "Sorted at the village hub" },
];

export default function Hero() {
  const wrapRef = useRef<HTMLDivElement>(null);
  const headlineRef = useRef<HTMLDivElement>(null);
  const subRef = useRef<HTMLDivElement>(null);
  const imgRef = useRef<HTMLDivElement>(null);
  const badgeRef = useRef<HTMLDivElement>(null);
  const [openSpot, setOpenSpot] = useState<number | null>(null);

  useEffect(() => {
    const { gsap, ScrollTrigger } = ensureGsap();
    const ctx = gsap.context(() => {
      const tl = gsap.timeline({
        scrollTrigger: {
          trigger: wrapRef.current,
          start: "top top",
          end: "bottom top",
          scrub: 0.6,
        },
      });

      tl.to(headlineRef.current, { yPercent: -35, opacity: 0.15, scale: 0.92, ease: "none" }, 0)
        .to(subRef.current, { yPercent: -20, opacity: 0, ease: "none" }, 0)
        .to(imgRef.current, { yPercent: 12, ease: "none" }, 0);

      gsap.to(badgeRef.current, {
        rotate: 360,
        duration: 18,
        repeat: -1,
        ease: "none",
      });

      gsap.fromTo(
        headlineRef.current,
        { opacity: 0, y: 40 },
        { opacity: 1, y: 0, duration: 1.2, ease: "power3.out", delay: 0.2 }
      );
      gsap.fromTo(
        subRef.current,
        { opacity: 0, y: 20 },
        { opacity: 1, y: 0, duration: 1, ease: "power3.out", delay: 0.6 }
      );
    });
    return () => ctx.revert();
  }, []);

  return (
    <section id="hero" ref={wrapRef} className="relative h-[180vh] bg-primary-900">
      <div className="sticky top-0 h-screen overflow-hidden">
        {/* full-bleed photo background */}
        <div ref={imgRef} className="absolute inset-0 scale-110">
          <Image
            src="/images/hero/main.jpg"
            alt="Sunrise over Maharashtra farmland"
            fill
            priority
            sizes="100vw"
            className="object-cover"
          />
        </div>
        <div className="absolute inset-0 bg-gradient-to-t from-primary-900 via-primary-900/50 to-primary-900/30" />
        <div className="absolute inset-0 bg-gradient-to-r from-primary-900/90 via-primary-900/20 to-transparent" />
        <div className="absolute inset-0 bg-primary-900/10" />

        {/* hotspots */}
        {HOTSPOTS.map((spot, i) => (
          <div
            key={spot.label}
            className="absolute z-20 hidden sm:block"
            style={{ top: spot.top, left: spot.left }}
          >
            <button
              aria-label={spot.label}
              onClick={() => setOpenSpot(openSpot === i ? null : i)}
              onMouseEnter={() => setOpenSpot(i)}
              onMouseLeave={() => setOpenSpot(null)}
              className="relative flex h-8 w-8 items-center justify-center rounded-full border border-neutral-100/70 bg-primary-900/40 text-neutral-100 backdrop-blur-sm transition-transform hover:scale-110"
            >
              <span className="absolute h-full w-full animate-ping rounded-full bg-secondary-400/40" />
              <span className="relative h-1.5 w-1.5 rounded-full bg-secondary-400" />
            </button>
            {openSpot === i && (
              <div className="absolute left-1/2 top-10 w-44 -translate-x-1/2 rounded-lg bg-neutral-100 px-3 py-2 text-center text-xs font-semibold text-primary-800 shadow-xl">
                {spot.label}
              </div>
            )}
          </div>
        ))}

        {/* content */}
        <div className="relative z-10 mx-auto flex h-full max-w-7xl flex-col justify-center px-5 sm:px-8">
          <p className="eyebrow mb-4 text-secondary-400 sm:mb-6">Local Nagpur Connection</p>
          <div ref={headlineRef} className="pb-2">
            <h1 className="font-display text-[13vw] font-bold leading-[1.15] text-neutral-100 sm:text-[9vw] lg:text-[7.5rem]">
              Proudly
              <br />
              Serving{" "}
              <span className="font-script italic text-secondary-400">Nagpur</span>
            </h1>
          </div>
          <div ref={subRef} className="mt-6 max-w-xl sm:mt-8">
            <p className="text-base leading-relaxed text-neutral-100/80 sm:text-lg">
              Gawacha Bazaar is Nagpur&apos;s very own — a local team cutting out the
              middleman between family farms across Maharashtra and your kitchen.
            </p>
            <div className="mt-8 flex flex-wrap items-center gap-4">
              <RippleButton
                as="a"
                href="#app"
                rippleColor="rgba(11,45,32,0.35)"
                className="rounded-full bg-secondary-500 px-7 py-3.5 text-xs font-bold uppercase tracking-widest text-primary-900 transition-transform hover:scale-105"
              >
                Get the App
              </RippleButton>
              <a
                href="#story"
                className="eyebrow text-neutral-100/70 underline decoration-secondary-500/60 underline-offset-4 hover:text-neutral-100"
              >
                Our Story
              </a>
            </div>
          </div>
        </div>

        {/* rotating badge */}
        <div
          ref={badgeRef}
          className="absolute bottom-10 right-6 hidden h-28 w-28 items-center justify-center sm:right-10 sm:flex"
        >
          <svg viewBox="0 0 100 100" className="h-full w-full">
            <defs>
              <path id="heroCircle" d="M50,50 m-38,0 a38,38 0 1,1 76,0 a38,38 0 1,1 -76,0" />
            </defs>
            <text fill="#D9A52A" fontSize="8.6" letterSpacing="2" className="uppercase font-sans font-semibold">
              <textPath href="#heroCircle">
                {"• FRESH DAILY • ZERO MIDDLEMEN • VILLAGE GRADED "}
              </textPath>
            </text>
          </svg>
          <span className="absolute h-3 w-3 rounded-full bg-secondary-500" />
        </div>

        <div className="absolute bottom-8 left-5 flex items-center gap-2 text-neutral-100/60 sm:left-8 md:left-32">
          <span className="h-8 w-px bg-neutral-100/40" />
          <span className="text-[10px] font-semibold uppercase tracking-[0.3em]">Scroll</span>
        </div>
      </div>
    </section>
  );
}
