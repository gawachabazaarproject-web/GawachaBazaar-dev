"use client";

import { useEffect, useRef, useState } from "react";
import Image from "next/image";
import { ensureGsap } from "@/lib/gsap";
import { IconVillage, IconCheckBadge, IconWarehouse, IconGrain, IconMapPin } from "./icons";

const ITEMS = [
  {
    title: "Village Sourced",
    desc: "Every order traces back to a named partner farm, not an anonymous wholesaler.",
    icon: IconVillage,
    img: "/images/why/01-village.jpg",
  },
  {
    title: "Hand Graded Daily",
    desc: "Nothing ships until it's sorted and graded by hand at the village hub.",
    icon: IconCheckBadge,
    img: "/images/why/02-graded.jpg",
  },
  {
    title: "Zero Cold Storage",
    desc: "Produce moves same-day — no multi-day warehouse holds to dull the freshness.",
    icon: IconWarehouse,
    img: "/images/why/03-cold.jpg",
  },
  {
    title: "Fair Farmer Pricing",
    desc: "Cutting out layers of middlemen means growers keep more of every rupee.",
    icon: IconGrain,
    img: "/images/why/04-pricing.jpg",
  },
  {
    title: "Live Order Tracking",
    desc: "Watch your order move from bazaar hub to rider to your doorstep, in real time.",
    icon: IconMapPin,
    img: "/images/why/05-tracking.jpg",
  },
];

export default function WhyChooseUs() {
  const wrapperRef = useRef<HTMLDivElement>(null);
  const [active, setActive] = useState(0);

  useEffect(() => {
    const { ScrollTrigger } = ensureGsap();
    const st = ScrollTrigger.create({
      trigger: wrapperRef.current,
      start: "top top",
      end: `+=${ITEMS.length * 70}%`,
      pin: true,
      onUpdate: (self) => {
        setActive(Math.min(ITEMS.length - 1, Math.floor(self.progress * ITEMS.length)));
      },
    });
    return () => st.kill();
  }, []);

  return (
    <section ref={wrapperRef} className="relative h-screen overflow-hidden bg-neutral-100">
      <div className="mx-auto grid h-full max-w-7xl grid-cols-1 items-center gap-10 px-5 sm:px-8 lg:grid-cols-2">
        <div>
          <p className="eyebrow text-primary-600">Why Nagpur Trusts Us</p>
          <div className="mt-8 flex flex-col">
            {ITEMS.map((item, i) => (
              <div
                key={item.title}
                className={`border-b border-primary-800/10 py-5 transition-all duration-500 ${
                  i === active ? "opacity-100" : "opacity-35"
                }`}
              >
                <h3
                  className={`font-display text-xl font-semibold transition-colors duration-500 sm:text-2xl ${
                    i === active ? "text-primary-800" : "text-primary-800/60"
                  }`}
                >
                  <span className="mr-3 text-sm text-secondary-500">{String(i + 1).padStart(2, "0")}</span>
                  {item.title}
                </h3>
                {i === active && (
                  <p className="mt-2 max-w-md text-sm leading-relaxed text-primary-700/70">{item.desc}</p>
                )}
              </div>
            ))}
          </div>
        </div>

        <div className="relative hidden aspect-[4/5] w-full max-w-md overflow-hidden rounded-none bg-primary-800 sm:mx-auto lg:block">
          {ITEMS.map((item, i) => (
            <div
              key={item.title}
              className="absolute inset-0 transition-opacity duration-700 ease-out"
              style={{ opacity: i === active ? 1 : 0 }}
            >
              <Image src={item.img} alt={item.title} fill sizes="420px" className="object-cover" />
              <div className="absolute inset-0 bg-gradient-to-t from-primary-900/90 via-transparent to-primary-900/10" />
            </div>
          ))}

          <div className="absolute inset-6 rounded-none border border-secondary-500/25" />

          <div className="absolute bottom-8 left-8 right-8 flex items-end justify-between">
            <div>
              <span className="font-deva text-base text-secondary-400/90">गावाचा बाजार</span>
              <p className="mt-1 font-display text-lg font-semibold text-neutral-100">
                {ITEMS[active].title}
              </p>
            </div>
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-secondary-500/90">
              {(() => {
                const ActiveIcon = ITEMS[active].icon;
                return <ActiveIcon className="h-6 w-6 text-primary-900" />;
              })()}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
