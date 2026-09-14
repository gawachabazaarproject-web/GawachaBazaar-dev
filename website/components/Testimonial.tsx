"use client";

import { useEffect, useRef } from "react";
import Image from "next/image";
import { ensureGsap } from "@/lib/gsap";

export default function Testimonial() {
  const sectionRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const { gsap } = ensureGsap();
    const ctx = gsap.context(() => {
      gsap.from(".quote-mark", {
        scale: 0.6,
        opacity: 0,
        duration: 0.8,
        ease: "back.out(1.7)",
        scrollTrigger: { trigger: sectionRef.current, start: "top 70%" },
      });
      gsap.from(".quote-text", {
        y: 30,
        opacity: 0,
        duration: 1,
        delay: 0.15,
        ease: "power3.out",
        scrollTrigger: { trigger: sectionRef.current, start: "top 70%" },
      });
      gsap.from(".quote-cite", {
        y: 15,
        opacity: 0,
        duration: 0.8,
        delay: 0.4,
        ease: "power3.out",
        scrollTrigger: { trigger: sectionRef.current, start: "top 70%" },
      });
    }, sectionRef);
    return () => ctx.revert();
  }, []);

  return (
    <section ref={sectionRef} className="relative flex h-[85vh] min-h-[560px] items-center overflow-hidden bg-primary-900">
      <Image
        src="/images/people/testimonial.jpg"
        alt="A family preparing a fresh Gawacha Bazaar delivery in their kitchen"
        fill
        sizes="100vw"
        className="object-cover"
      />
      <div className="absolute inset-0 bg-primary-900/80" />
      <div className="absolute inset-0 bg-gradient-to-t from-primary-900 via-transparent to-primary-900/40" />

      <div className="relative z-10 mx-auto max-w-4xl px-6 text-center sm:px-8">
        <span className="quote-mark mx-auto mb-6 flex h-14 w-14 items-center justify-center rounded-full border border-secondary-500/50 font-display text-3xl text-secondary-400">
          &ldquo;
        </span>
        <p className="quote-text font-display text-2xl font-medium leading-snug text-neutral-100 sm:text-4xl">
          My grandmother says these vegetables taste like the ones from her own village —
          not the ones from the cold-store bins we used to get.
        </p>
        <p className="quote-cite eyebrow mt-8 text-secondary-400">
          Anjali Deshmukh <span className="text-neutral-100/40">— Wardhaman Nagar, Nagpur</span>
        </p>
      </div>
    </section>
  );
}
