"use client";

import { useEffect, useRef, useState } from "react";
import Image from "next/image";
import { ensureGsap } from "@/lib/gsap";
import {
  IconSprout,
  IconCrate,
  IconCheckBadge,
  IconWarehouse,
  IconFruit,
  IconCart,
  IconPayment,
  IconTruck,
  IconBike,
  IconHeart,
} from "./icons";

const STEPS = [
  {
    icon: IconSprout,
    title: "Farm",
    desc: "Farm details are recorded and verified.",
    img: "/images/journey/01-farm.jpg",
  },
  {
    icon: IconCrate,
    title: "Harvest & Batch",
    desc: "Each harvest is logged as a traceable batch.",
    img: "/images/journey/02-harvest.jpg",
  },
  {
    icon: IconCheckBadge,
    title: "Quality Check",
    desc: "Every batch is graded before it travels.",
    img: "/images/journey/03-quality.jpg",
  },
  {
    icon: IconWarehouse,
    title: "Inventory at Hub",
    desc: "Stock lands at the Gawacha transit node.",
    img: "/images/journey/04-inventory.jpg",
  },
  {
    icon: IconFruit,
    title: "Product",
    desc: "Produce is listed fresh in the bazaar catalog.",
    img: "/images/journey/05-product.jpg",
  },
  {
    icon: IconCart,
    title: "Customer Orders",
    desc: "You add it to cart and place your order.",
    img: "/images/journey/06-orders.jpg",
  },
  {
    icon: IconPayment,
    title: "Payment",
    desc: "Payment is processed and recorded securely.",
    img: "/images/journey/07-payment.jpg",
  },
  {
    icon: IconTruck,
    title: "Fulfillment",
    desc: "Order is picked, packed, and staged for transit.",
    img: "/images/journey/08-fulfillment.jpg",
  },
  {
    icon: IconBike,
    title: "Delivery",
    desc: "A local rider carries it the last mile, live-tracked.",
    img: "/images/journey/09-delivery.jpg",
  },
  {
    icon: IconHeart,
    title: "Happy Customer",
    desc: "Delivered fresh — every step, traceable.",
    img: "/images/journey/10-happy.jpg",
  },
];

export default function Traceability() {
  const wrapperRef = useRef<HTMLDivElement>(null);
  const trackRef = useRef<HTMLDivElement>(null);
  const barRef = useRef<HTMLDivElement>(null);
  const [active, setActive] = useState(0);

  useEffect(() => {
    const { gsap, ScrollTrigger } = ensureGsap();
    const ctx = gsap.context(() => {
      const track = trackRef.current;
      const wrapper = wrapperRef.current;
      if (!track || !wrapper) return;

      const distance = () => track.scrollWidth - window.innerWidth;

      const tween = gsap.to(track, {
        x: () => -distance(),
        ease: "none",
        scrollTrigger: {
          trigger: wrapper,
          start: "top top",
          end: () => `+=${distance()}`,
          scrub: 1,
          pin: true,
          invalidateOnRefresh: true,
          onUpdate: (self) => {
            if (barRef.current) barRef.current.style.width = `${self.progress * 100}%`;
            setActive(Math.round(self.progress * (STEPS.length - 1)));
          },
        },
      });

      return () => {
        tween.scrollTrigger?.kill();
        tween.kill();
      };
    }, wrapperRef);
    return () => ctx.revert();
  }, []);

  return (
    <section id="journey" ref={wrapperRef} data-nav-theme="dark" className="relative h-screen overflow-hidden bg-tertiary-800">
      <div className="pointer-events-none absolute inset-0 opacity-[0.06]">
        <div className="h-full w-full bg-[radial-gradient(circle_at_20%_20%,_white_1px,_transparent_1px)] bg-[length:28px_28px]" />
      </div>

      <div className="relative z-10 mx-auto flex h-full max-w-[1600px] flex-col justify-start gap-6 px-5 py-16 sm:justify-center sm:gap-8 sm:px-8 sm:py-24">
        <div className="shrink-0">
          <p className="eyebrow text-secondary-400">Farm-to-Home Traceability</p>
          <h2 className="mt-3 max-w-2xl font-display text-xl font-semibold leading-snug text-neutral-100 sm:text-4xl lg:text-5xl">
            Every step is connected. Every story is stored.
          </h2>
          <div className="mt-5 h-px w-full max-w-xl bg-neutral-100/20">
            <div ref={barRef} className="h-px w-0 bg-secondary-500" />
          </div>
          <p className="eyebrow mt-2 text-neutral-100/40">
            {String(active + 1).padStart(2, "0")} / {String(STEPS.length).padStart(2, "0")} —{" "}
            {STEPS[active]?.title}
          </p>
        </div>

        <div className="relative min-h-0 flex-1">
          <div ref={trackRef} className="flex h-full items-center gap-5 will-change-transform sm:gap-7">
            {STEPS.map((step, i) => (
              <div
                key={step.title}
                className={`relative flex h-[46vh] max-h-[440px] w-[240px] shrink-0 flex-col overflow-hidden rounded-none border transition-all duration-500 sm:h-[62vh] sm:w-[300px] lg:w-[340px] ${
                  i === active
                    ? "scale-100 border-secondary-500/70 opacity-100"
                    : "scale-[0.94] border-neutral-100/10 opacity-60"
                }`}
              >
                <div className="relative h-3/5 w-full">
                  <Image
                    src={step.img}
                    alt={step.title}
                    fill
                    sizes="340px"
                    className="object-cover"
                  />
                  <div className="absolute inset-x-0 bottom-0 h-24 bg-gradient-to-t from-primary-900/90 to-transparent" />
                  <div className="absolute inset-0 ring-1 ring-inset ring-white/10" />
                  <span className="absolute left-4 top-4 flex h-9 w-9 items-center justify-center rounded-full bg-secondary-500 text-xs font-bold text-primary-900">
                    {String(i + 1).padStart(2, "0")}
                  </span>
                  <step.icon
                    className={`absolute bottom-4 right-4 h-7 w-7 transition-colors ${
                      i === active ? "text-secondary-400" : "text-neutral-100/70"
                    }`}
                  />
                </div>
                <div className="flex flex-1 flex-col justify-center bg-primary-800 px-5 py-5">
                  <h3 className="font-display text-lg font-semibold text-neutral-100">{step.title}</h3>
                  <p className="mt-1.5 text-sm leading-relaxed text-neutral-100/50">{step.desc}</p>
                </div>
              </div>
            ))}
            <div className="flex h-[62vh] max-h-[440px] w-[240px] shrink-0 items-center justify-center sm:w-[300px]">
              <p className="font-script italic text-3xl text-secondary-400">every story, stored.</p>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
