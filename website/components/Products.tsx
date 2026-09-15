"use client";

import { useEffect, useRef } from "react";
import Image from "next/image";
import { ensureGsap } from "@/lib/gsap";
import { IconLeaf, IconFruit, IconGrain, IconDairy } from "./icons";
import EditorialLink from "./EditorialLink";
import ChapterMark from "./ChapterMark";

const CATEGORIES = [
  { icon: IconLeaf, title: "Vegetables", desc: "Leafy greens & daily veg, cut fresh at dawn.", img: "/images/bg/carrots.jpg" },
  { icon: IconFruit, title: "Fruits", desc: "Seasonal fruit picked ripe from partner orchards.", img: "/images/bg/peppers.jpg" },
  { icon: IconGrain, title: "Grains & Pulses", desc: "Stone-cleaned staples straight from the village mill.", img: "/images/bg/grains.jpg" },
  { icon: IconDairy, title: "Dairy & More", desc: "Farm dairy and pantry essentials, sourced locally.", img: "/images/bg/dairy.jpg" },
];

export default function Products() {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const { gsap } = ensureGsap();
    const ctx = gsap.context(() => {
      gsap.from(".cat-card", {
        y: 50,
        opacity: 0,
        duration: 0.7,
        stagger: 0.1,
        ease: "power3.out",
        scrollTrigger: { trigger: ref.current, start: "top 75%" },
      });
    }, ref);
    return () => ctx.revert();
  }, []);

  return (
    <section id="products" ref={ref} data-nav-theme="light" className="relative overflow-hidden bg-neutral-100 py-24 sm:py-32">
      <ChapterMark index={8} className="absolute left-0 top-2 sm:top-4" />
      <div className="relative mx-auto max-w-7xl px-5 sm:px-8">
        <div className="flex flex-col items-start justify-between gap-6 sm:flex-row sm:items-end">
          <div>
            <p className="eyebrow text-primary-600">08 / 08 — What&apos;s in the Bazaar</p>
            <h2 className="mt-3 max-w-xl font-display text-3xl font-semibold text-primary-800 sm:text-5xl">
              Village fresh, sorted into every basket.
            </h2>
          </div>
          <EditorialLink as="a" href="#app" tone="dark">
            Browse The App
          </EditorialLink>
        </div>

        <div className="mt-14 grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {CATEGORIES.map((cat) => (
            <div
              key={cat.title}
              className="cat-card group relative aspect-[3/4] overflow-hidden rounded-none transition-transform hover:-translate-y-1"
            >
              <Image
                src={cat.img}
                alt={cat.title}
                fill
                sizes="(min-width: 1024px) 25vw, (min-width: 640px) 50vw, 100vw"
                className="object-cover transition-transform duration-700 group-hover:scale-110"
              />
              <div className="absolute inset-0 bg-gradient-to-t from-primary-900/90 via-primary-900/25 to-primary-900/10" />

              <div className="absolute inset-0 flex flex-col justify-between p-6">
                <div className="flex h-12 w-12 items-center justify-center rounded-none bg-secondary-500/90 text-primary-900">
                  <cat.icon className="h-6 w-6" />
                </div>
                <div>
                  <h3 className="font-display text-xl font-semibold text-neutral-100">{cat.title}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-neutral-100/70">{cat.desc}</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
