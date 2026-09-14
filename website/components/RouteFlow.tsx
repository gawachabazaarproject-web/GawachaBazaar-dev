"use client";

import { useEffect, useRef } from "react";
import { ensureGsap } from "@/lib/gsap";
import { IconVillage, IconWarehouse, IconMapPin, IconHome } from "./icons";
import ChapterMark from "./ChapterMark";

const STEPS = [
  {
    icon: IconVillage,
    tag: "गाव",
    title: "Village Nodes",
    desc: "Produce harvested at dawn from family farms across Maharashtra.",
  },
  {
    icon: IconWarehouse,
    tag: "बजार",
    title: "Bazaar Hub",
    desc: "Cleaned, graded, and packed at our local sorting nodes.",
  },
  {
    icon: IconMapPin,
    tag: "नागपूर",
    title: "Nagpur City",
    desc: "Direct transit to city nodes, avoiding long warehouse stops.",
  },
  {
    icon: IconHome,
    tag: "घर",
    title: "Your Home",
    desc: "Fresh delivery by our riders straight to your doorstep.",
  },
];

export default function RouteFlow() {
  const sectionRef = useRef<HTMLDivElement>(null);
  const pathRef = useRef<SVGPathElement>(null);
  const dotRef = useRef<SVGCircleElement>(null);

  useEffect(() => {
    const { gsap, ScrollTrigger } = ensureGsap();
    const ctx = gsap.context(() => {
      const path = pathRef.current;
      if (!path) return;
      const len = path.getTotalLength();
      gsap.set(path, { strokeDasharray: len, strokeDashoffset: len });

      const tl = gsap.timeline({
        scrollTrigger: {
          trigger: sectionRef.current,
          start: "top 70%",
          end: "bottom 60%",
          scrub: 0.8,
        },
      });

      tl.to(path, { strokeDashoffset: 0, ease: "none" });
      if (dotRef.current) {
        tl.to(
          dotRef.current,
          {
            motionPath: {
              path,
              align: path,
              alignOrigin: [0.5, 0.5],
            },
            ease: "none",
          },
          0
        );
      }

      gsap.utils.toArray<HTMLElement>(".flow-card").forEach((card, i) => {
        gsap.from(card, {
          y: 40,
          opacity: 0,
          duration: 0.7,
          ease: "power3.out",
          delay: i * 0.08,
          scrollTrigger: { trigger: card, start: "top 88%" },
        });
      });
    }, sectionRef);
    return () => ctx.revert();
  }, []);

  return (
    <section id="story" ref={sectionRef} className="relative overflow-hidden bg-neutral-100 py-24 sm:py-32">
      <ChapterMark index={2} className="absolute left-0 top-2 sm:top-4" />
      <div className="relative mx-auto max-w-7xl px-5 sm:px-8">
        <p className="eyebrow text-primary-600">02 / 08 — The Direct Route</p>
        <h2 className="mt-3 max-w-2xl font-display text-3xl font-semibold leading-tight text-primary-800 sm:text-5xl">
          From rural block to your gate — four honest steps.
        </h2>

        <div className="mt-16 grid grid-cols-1 gap-8 sm:grid-cols-2 lg:grid-cols-4">
          {STEPS.map((step, i) => (
            <div key={step.title} className="flow-card relative">
              <div className="flex h-16 w-16 items-center justify-center rounded-none bg-primary-800 text-secondary-400">
                <step.icon className="h-8 w-8" />
              </div>
              <span className="absolute right-0 top-0 flex h-6 w-6 items-center justify-center rounded-full bg-secondary-500 text-[11px] font-bold text-primary-900">
                {i + 1}
              </span>
              <h3 className="mt-5 font-display text-xl font-semibold text-primary-800">
                {step.title} <span className="font-deva text-secondary-500">{step.tag}</span>
              </h3>
              <p className="mt-2 text-sm leading-relaxed text-primary-700/70">{step.desc}</p>
            </div>
          ))}
        </div>

        {/* schematic route */}
        <div className="relative mt-20 rounded-none border border-primary-800/10 bg-white/60 px-6 py-14 sm:px-14">
          <svg viewBox="0 0 800 120" className="w-full overflow-visible" preserveAspectRatio="none">
            <path
              ref={pathRef}
              d="M20,90 C 150,20 220,110 320,60 S 480,10 560,55 700,90 780,40"
              fill="none"
              stroke="#0B2D20"
              strokeWidth="2"
              strokeLinecap="round"
            />
            <circle ref={dotRef} r="7" fill="#D9A52A" />
          </svg>
          <div className="mt-6 flex flex-col justify-between gap-8 text-center sm:flex-row">
            <div>
              <p className="font-display text-lg font-semibold text-primary-800">Rural Nagpur Blocks</p>
              <p className="eyebrow mt-1 text-primary-500/60">Harvest at dawn</p>
            </div>
            <div>
              <p className="font-display text-lg font-semibold text-primary-800">Gawacha Transit Node</p>
              <p className="eyebrow mt-1 text-primary-500/60">Sort · grade · pack</p>
            </div>
            <div>
              <p className="font-display text-lg font-semibold text-primary-800">Nagpur City Deliveries</p>
              <p className="eyebrow mt-1 text-primary-500/60">Same-day, doorstep</p>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
