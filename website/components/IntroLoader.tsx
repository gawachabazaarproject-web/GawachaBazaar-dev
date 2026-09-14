"use client";

import { useEffect, useRef, useState } from "react";
import Image from "next/image";
import { ensureGsap } from "@/lib/gsap";

export default function IntroLoader() {
  const [done, setDone] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const logoRef = useRef<HTMLDivElement>(null);
  const line1Ref = useRef<HTMLDivElement>(null);
  const line2Ref = useRef<HTMLDivElement>(null);
  const subRef = useRef<HTMLParagraphElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (sessionStorage.getItem("gb-intro-seen")) {
      setDone(true);
      return;
    }
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    document.body.style.overflow = "hidden";

    const { gsap } = ensureGsap();

    const finish = () => {
      document.body.style.overflow = "";
      sessionStorage.setItem("gb-intro-seen", "1");
      setDone(true);
    };

    if (reduced) {
      finish();
      return;
    }

    const tl = gsap.timeline({ onComplete: finish });

    tl.set([line1Ref.current, line2Ref.current], { clipPath: "inset(0 0 100% 0)" })
      .set(logoRef.current, { opacity: 0, scale: 0.85 })
      .set(subRef.current, { opacity: 0, y: 12 })
      .to(logoRef.current, { opacity: 1, scale: 1, duration: 1, ease: "power2.out" }, 0.15)
      .to(line1Ref.current, { clipPath: "inset(0 0 0% 0)", duration: 1, ease: "expo.out" }, 0.55)
      .to(line2Ref.current, { clipPath: "inset(0 0 0% 0)", duration: 1, ease: "expo.out" }, 0.72)
      .to(subRef.current, { opacity: 1, y: 0, duration: 0.8, ease: "power2.out" }, 1.3)
      .to({}, { duration: 0.55 })
      .to(
        panelRef.current,
        { yPercent: -100, duration: 1.1, ease: "power3.inOut" },
        ">"
      );

    return () => {
      tl.kill();
      document.body.style.overflow = "";
    };
  }, []);

  if (done) return null;

  return (
    <div ref={rootRef} className="fixed inset-0 z-[100]" aria-hidden>
      <div ref={panelRef} className="flex h-full w-full flex-col items-center justify-center gap-8 bg-primary-900">
        <div ref={logoRef} className="flex flex-col items-center gap-5">
          <Image
            src="/images/logo.jpeg"
            alt=""
            width={56}
            height={56}
            className="h-14 w-14 rounded-full object-cover ring-1 ring-secondary-500/50"
          />
          <div className="text-center">
            <div ref={line1Ref} className="overflow-hidden">
              <p className="font-display text-[13vw] font-bold leading-[0.95] text-neutral-100 sm:text-7xl">
                Gawacha
              </p>
            </div>
            <div ref={line2Ref} className="overflow-hidden">
              <p className="font-script text-[13vw] italic leading-[1.1] text-secondary-400 sm:text-7xl">
                Bazaar
              </p>
            </div>
          </div>
        </div>
        <p ref={subRef} className="eyebrow text-neutral-100/50">
          Village Fresh — Since Nagpur
        </p>
      </div>
    </div>
  );
}
