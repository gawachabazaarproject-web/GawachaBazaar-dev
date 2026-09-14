"use client";

import { useEffect, useRef } from "react";
import { ensureGsap } from "@/lib/gsap";
import RippleButton from "./RippleButton";

export default function AppCTA() {
  const badgeRef = useRef<HTMLDivElement>(null);
  const sectionRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const { gsap } = ensureGsap();
    const ctx = gsap.context(() => {
      gsap.to(badgeRef.current, { rotate: 360, duration: 16, repeat: -1, ease: "none" });
      gsap.from(".app-copy > *", {
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
    <section id="app" ref={sectionRef} className="relative overflow-hidden bg-primary-800 py-28 sm:py-36">
      <span
        aria-hidden
        className="pointer-events-none absolute -bottom-10 left-1/2 -translate-x-1/2 select-none font-display text-[26vw] font-bold text-neutral-100/[0.03] sm:text-[18vw]"
      >
        BAZAAR
      </span>

      <div className="relative mx-auto flex max-w-5xl flex-col items-center px-5 text-center sm:px-8">
        <div className="app-copy flex flex-col items-center">
          <p className="eyebrow text-secondary-400">Fresh Is One Tap Away</p>
          <h2 className="mt-4 font-display text-4xl font-bold leading-[1.05] text-neutral-100 sm:text-6xl">
            Village fresh, <span className="font-script italic text-secondary-400">yours</span> this evening.
          </h2>
          <p className="mt-6 max-w-lg text-base leading-relaxed text-neutral-100/70 sm:text-lg">
            Download Gawacha Bazaar and order straight from Nagpur&apos;s village nodes —
            fresh produce, transparent pricing, live tracking.
          </p>
          <div className="mt-10 flex flex-wrap items-center justify-center gap-4">
            <RippleButton
              as="a"
              href="#contact"
              rippleColor="rgba(11,45,32,0.35)"
              className="rounded-full bg-secondary-500 px-8 py-4 text-xs font-bold uppercase tracking-widest text-primary-900 transition-transform hover:scale-105"
            >
              Download for Android
            </RippleButton>
            <RippleButton
              as="a"
              href="#contact"
              rippleColor="rgba(217,165,42,0.4)"
              className="rounded-full border border-neutral-100/30 px-8 py-4 text-xs font-bold uppercase tracking-widest text-neutral-100 transition-colors hover:border-secondary-500 hover:text-secondary-400"
            >
              Download for iOS
            </RippleButton>
          </div>
        </div>

        <div ref={badgeRef} className="relative mt-16 hidden h-32 w-32 items-center justify-center sm:flex">
          <svg viewBox="0 0 100 100" className="h-full w-full">
            <defs>
              <path id="ctaCircle" d="M50,50 m-38,0 a38,38 0 1,1 76,0 a38,38 0 1,1 -76,0" />
            </defs>
            <text fill="#D9A52A" fontSize="8.4" letterSpacing="2" className="uppercase font-sans font-semibold">
              <textPath href="#ctaCircle">{"• GET THE APP • ORDER FRESH TODAY "}</textPath>
            </text>
          </svg>
          <span className="absolute h-3 w-3 rounded-full bg-secondary-500" />
        </div>
      </div>
    </section>
  );
}
