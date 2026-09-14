"use client";

import { useEffect, useRef } from "react";
import Image from "next/image";
import { ensureGsap } from "@/lib/gsap";

const TILES = [
  { src: "/images/gallery/market-wide.jpg", alt: "Crates of fresh vegetables sorted at a village hub", label: "Sorted at the hub", className: "lg:col-span-2 lg:row-span-2", parallax: 40 },
  { src: "/images/gallery/mango.jpg", alt: "Rows of ripe mangoes", label: "Mango season", className: "lg:row-span-2", parallax: -60 },
  { src: "/images/gallery/orange.jpg", alt: "Fresh oranges piled together", label: "Citrus, hand-picked", parallax: 30 },
  { src: "/images/gallery/watermelon.jpg", alt: "A fresh watermelon slice", label: "Summer favourite", parallax: -35 },
  { src: "/images/gallery/berries.jpg", alt: "A mix of fresh berries", label: "Small batch berries", parallax: 50 },
  { src: "/images/gallery/greens.jpg", alt: "Fresh spinach leaves", label: "Leafy & local", parallax: -25 },
];

export default function FreshGallery() {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const { gsap } = ensureGsap();
    const ctx = gsap.context(() => {
      gsap.from(".gallery-heading > *", {
        y: 24,
        opacity: 0,
        duration: 0.7,
        stagger: 0.08,
        ease: "power3.out",
        scrollTrigger: { trigger: ref.current, start: "top 80%" },
      });

      gsap.utils.toArray<HTMLElement>(".gallery-tile").forEach((tile, i) => {
        const img = tile.querySelector(".gallery-img");

        gsap.fromTo(
          tile,
          { clipPath: "inset(22% 22% 22% 22% round 0px)", opacity: 0.4 },
          {
            clipPath: "inset(0% 0% 0% 0% round 0px)",
            opacity: 1,
            ease: "none",
            scrollTrigger: {
              trigger: tile,
              start: "top 95%",
              end: "top 55%",
              scrub: 0.6,
            },
          }
        );

        gsap.fromTo(
          img,
          { scale: 1.45 },
          {
            scale: 1,
            ease: "none",
            scrollTrigger: {
              trigger: tile,
              start: "top 95%",
              end: i % 2 === 0 ? "bottom 10%" : "bottom 35%",
              scrub: 0.8,
            },
          }
        );
      });
    }, ref);
    return () => ctx.revert();
  }, []);

  return (
    <section ref={ref} className="overflow-hidden bg-neutral-100 py-24 sm:py-32">
      <div className="mx-auto max-w-7xl px-5 sm:px-8">
        <div className="gallery-heading mx-auto max-w-2xl text-center">
          <p className="eyebrow text-primary-600">Straight From The Crate</p>
          <h2 className="mt-4 font-display text-3xl font-bold text-primary-800 sm:text-5xl">
            Fresh, <span className="font-script italic text-secondary-600">in focus.</span>
          </h2>
          <p className="mt-5 text-sm leading-relaxed text-primary-700/60 sm:text-base">
            Every color on your plate started as a color in someone&apos;s field. This is what
            that looks like, up close.
          </p>
        </div>

        <div className="mt-14 grid grid-cols-2 auto-rows-[180px] gap-3 sm:auto-rows-[220px] sm:gap-4 lg:grid-cols-4 lg:auto-rows-[240px]">
          {TILES.map((tile) => (
            <div
              key={tile.src}
              className={`gallery-tile group relative overflow-hidden rounded-none ${tile.className ?? ""}`}
            >
              <div className="gallery-img absolute inset-0 h-full w-full">
                <Image
                  src={tile.src}
                  alt={tile.alt}
                  fill
                  sizes="(min-width: 1024px) 25vw, 50vw"
                  className="object-cover transition-transform duration-700 group-hover:scale-110"
                />
              </div>
              <div className="absolute inset-0 bg-gradient-to-t from-primary-900/80 via-primary-900/0 to-transparent" />
              <span className="absolute bottom-3 left-3 text-xs font-semibold uppercase tracking-wider text-neutral-100">
                {tile.label}
              </span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
