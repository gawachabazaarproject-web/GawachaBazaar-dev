"use client";

import { useEffect, useRef } from "react";
import Lenis from "lenis";
import { ensureGsap } from "@/lib/gsap";

export default function SmoothScroll({ children }: { children: React.ReactNode }) {
  const counterRef = useRef<HTMLSpanElement>(null);
  const barRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const { gsap, ScrollTrigger } = ensureGsap();

    const lenis = new Lenis({
      duration: 1.1,
      easing: (t: number) => 1 - Math.pow(1 - t, 3),
      smoothWheel: true,
    });

    lenis.on("scroll", ScrollTrigger.update);

    gsap.ticker.add((time) => {
      lenis.raf(time * 1000);
    });
    gsap.ticker.lagSmoothing(0);

    const handleAnchorClick = (e: MouseEvent) => {
      const anchor = (e.target as HTMLElement)?.closest('a[href^="#"]');
      if (!anchor) return;
      const href = anchor.getAttribute("href");
      if (!href || href === "#") return;
      const el = document.querySelector(href);
      if (!el) return;
      e.preventDefault();
      lenis.scrollTo(el as HTMLElement, {
        duration: 1.6,
        easing: (t: number) => 1 - Math.pow(1 - t, 4),
        offset: 0,
      });
    };
    document.addEventListener("click", handleAnchorClick);

    const progress = ScrollTrigger.create({
      trigger: document.documentElement,
      start: "top top",
      end: "bottom bottom",
      onUpdate: (self) => {
        const pct = Math.round(self.progress * 100);
        if (counterRef.current) {
          counterRef.current.textContent = String(pct).padStart(2, "0");
        }
        if (barRef.current) {
          barRef.current.style.height = `${self.progress * 100}%`;
        }
      },
    });

    return () => {
      progress.kill();
      lenis.destroy();
      document.removeEventListener("click", handleAnchorClick);
    };
  }, []);

  return (
    <>
      <div className="pointer-events-none fixed left-4 sm:left-6 top-0 z-40 hidden h-screen flex-col items-center justify-between pb-8 pt-28 md:flex">
        <div className="mix-blend-difference h-16 w-px bg-neutral-100/40" />
        <div className="flex flex-col items-center gap-3">
          <span
            ref={counterRef}
            className="font-sans text-[11px] font-semibold tracking-widest text-neutral-100/70 mix-blend-difference"
          >
            00
          </span>
          <div className="relative h-28 w-px overflow-hidden bg-neutral-100/20">
            <div
              ref={barRef}
              className="absolute left-0 top-0 w-px bg-secondary-500"
              style={{ height: "0%" }}
            />
          </div>
        </div>
        <span
          className="font-sans text-[11px] font-semibold tracking-widest text-neutral-100/70 mix-blend-difference"
          style={{ writingMode: "vertical-rl" }}
        >
          SCROLL
        </span>
      </div>
      {children}
    </>
  );
}
