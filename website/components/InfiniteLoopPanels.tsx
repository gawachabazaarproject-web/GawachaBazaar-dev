"use client";

import { useEffect, useRef } from "react";
import Image from "next/image";
import { ensureGsap } from "@/lib/gsap";

const PANELS = [
  {
    stat: "12,000+",
    label: "Nagpur households served",
    detail: "And growing — a new sector added most months.",
    img: "/images/gallery/market-wide.jpg",
  },
  {
    stat: "35 KM",
    label: "Furthest village node",
    detail: "Still reaches your kitchen the same evening.",
    img: "/images/bg/aerial.jpg",
  },
  {
    stat: "Zero",
    label: "Middlemen, ever",
    detail: "Straight from the grower to your gate.",
    img: "/images/bg/village.jpg",
  },
  {
    stat: "2024",
    label: "Founded in Nagpur",
    detail: "By a small team tired of stale mandi produce.",
    img: "/images/gallery/mango.jpg",
  },
  {
    stat: "FSSAI",
    label: "Registered, every hub",
    detail: "Licensed and available on request — no exceptions.",
    img: "/images/bg/hub.jpg",
  },
];

const TOTAL = PANELS.length;

export default function InfiniteLoopPanels() {
  const wrapperRef = useRef<HTMLDivElement>(null);
  const panelRefs = useRef<(HTMLDivElement | null)[]>([]);
  const counterRef = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    const { gsap, ScrollTrigger } = ensureGsap();
    const ctx = gsap.context(() => {
      const st = ScrollTrigger.create({
        trigger: wrapperRef.current,
        start: "top top",
        end: () => `+=${window.innerHeight * (TOTAL - 1)}`,
        pin: true,
        scrub: 0.7,
        snap: {
          snapTo: 1 / (TOTAL - 1),
          duration: 0.4,
          ease: "power2.inOut",
        },
        onUpdate: (self) => {
          const virtualIndex = self.progress * (TOTAL - 1);

          panelRefs.current.forEach((panel, i) => {
            if (!panel) return;
            // Plain linear offset — no circular wrap, so a panel never re-enters.
            const offset = i - virtualIndex;
            const abs = Math.abs(offset);
            gsap.set(panel, {
              yPercent: offset * 100,
              opacity: gsap.utils.clamp(0, 1, 1 - abs * 0.7),
              scale: gsap.utils.clamp(0.85, 1, 1 - abs * 0.12),
            });
          });

          const shown = Math.round(gsap.utils.clamp(0, TOTAL - 1, virtualIndex));
          if (counterRef.current) {
            counterRef.current.textContent = String(shown + 1).padStart(2, "0");
          }
        },
      });

      return () => st.kill();
    }, wrapperRef);
    return () => ctx.revert();
  }, []);

  return (
    <section ref={wrapperRef} data-nav-theme="dark" className="relative h-screen overflow-hidden bg-primary-900">
      <div className="pointer-events-none absolute inset-x-0 top-0 z-20 flex items-center justify-between px-5 pt-8 sm:px-8">
        <p className="eyebrow text-secondary-400">The Short Version</p>
        <p className="eyebrow text-neutral-100/40">
          <span ref={counterRef}>01</span> / {String(PANELS.length).padStart(2, "0")}
        </p>
      </div>

      {PANELS.map((panel, i) => (
        <div
          key={panel.stat + i}
          ref={(el) => {
            panelRefs.current[i] = el;
          }}
          className="absolute inset-0 flex items-center justify-center"
          style={{ willChange: "transform, opacity" }}
        >
          <div className="relative h-full w-full">
            <Image
              src={panel.img}
              alt={panel.label}
              fill
              sizes="100vw"
              className="object-cover"
              priority={i === 0}
            />
            <div className="absolute inset-0 bg-primary-900/75" />
            <div className="relative z-10 flex h-full flex-col items-center justify-center px-6 text-center">
              <span className="font-display text-[16vw] font-bold leading-none text-neutral-100 sm:text-[9rem]">
                {panel.stat}
              </span>
              <span className="mt-4 font-display text-xl italic text-secondary-400 sm:text-3xl">
                {panel.label}
              </span>
              <span className="mt-5 max-w-sm text-sm leading-relaxed text-neutral-100/60 sm:text-base">
                {panel.detail}
              </span>
            </div>
          </div>
        </div>
      ))}

      <div className="pointer-events-none absolute inset-x-0 bottom-8 z-20 flex justify-center">
        <span className="eyebrow text-neutral-100/40">Scroll To Cycle</span>
      </div>
    </section>
  );
}
