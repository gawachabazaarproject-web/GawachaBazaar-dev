"use client";

import { useEffect, useRef } from "react";
import { ensureGsap } from "@/lib/gsap";

const COLUMNS = [
  { label: "Founded", value: "2024", desc: "Started by a small team of Nagpur residents tired of stale mandi produce." },
  { label: "Compliance", value: "FSSAI Registered", desc: "Every hub operates under an active FSSAI license, available on request." },
  { label: "Coverage", value: "12,000+ Homes", desc: "Currently serving households across Nagpur, with new sectors added monthly." },
];

const STATEMENT =
  "Gawacha Bazaar is currently expanding its village-node network across Maharashtra, with new transit hubs planned for the districts surrounding Nagpur through 2026.";

export default function CompanyInfo() {
  const sectionRef = useRef<HTMLDivElement>(null);
  const words = STATEMENT.split(" ");

  useEffect(() => {
    const { gsap } = ensureGsap();
    const ctx = gsap.context(() => {
      gsap.utils.toArray<HTMLElement>(".info-col").forEach((col, i) => {
        gsap.from(col, {
          y: 30,
          opacity: 0,
          duration: 0.7,
          delay: i * 0.1,
          ease: "power3.out",
          scrollTrigger: { trigger: col, start: "top 85%" },
        });
      });

      gsap.to(".fade-word", {
        opacity: 1,
        stagger: 0.03,
        ease: "none",
        scrollTrigger: {
          trigger: ".fade-paragraph",
          start: "top 85%",
          end: "top 35%",
          scrub: 0.4,
        },
      });
    }, sectionRef);
    return () => ctx.revert();
  }, []);

  return (
    <section ref={sectionRef} data-nav-theme="light" className="bg-neutral-100 py-24 sm:py-32">
      <div className="mx-auto max-w-5xl px-5 text-center sm:px-8">
        <p className="eyebrow text-primary-600">A Place To Trust — Year After Year</p>

        <p className="fade-paragraph mx-auto mt-8 max-w-3xl font-display text-2xl font-medium leading-snug text-primary-800 sm:text-3xl">
          {words.map((word, i) => (
            <span key={i} className="fade-word opacity-15">
              {word}{" "}
            </span>
          ))}
        </p>

        <div className="mt-16 grid grid-cols-1 gap-10 border-t border-primary-800/10 pt-12 text-left sm:grid-cols-3">
          {COLUMNS.map((col) => (
            <div key={col.label} className="info-col">
              <p className="eyebrow text-secondary-600">{col.label}</p>
              <p className="mt-2 font-display text-2xl font-bold text-primary-800">{col.value}</p>
              <p className="mt-2 text-sm leading-relaxed text-primary-700/60">{col.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
