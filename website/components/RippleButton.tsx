"use client";

import { useRef, type MouseEvent, type ElementType, type ComponentPropsWithoutRef } from "react";
import { ensureGsap } from "@/lib/gsap";

type RippleOwnProps<T extends ElementType> = {
  as?: T;
  /** Color the circle sweeps in on hover. */
  fillColor?: string;
  /** Text color before hover. */
  textColor?: string;
  /** Text color once the fill has swept in. */
  hoverTextColor?: string;
  className?: string;
  children: React.ReactNode;
};

type RippleButtonProps<T extends ElementType> = RippleOwnProps<T> &
  Omit<ComponentPropsWithoutRef<T>, keyof RippleOwnProps<T>>;

export default function RippleButton<T extends ElementType = "button">({
  as,
  fillColor = "#05130D",
  textColor,
  hoverTextColor,
  className = "",
  children,
  onMouseEnter,
  onMouseLeave,
  ...rest
}: RippleButtonProps<T>) {
  const Comp = (as || "button") as ElementType;
  const hostRef = useRef<HTMLElement>(null);
  const circleRef = useRef<HTMLSpanElement>(null);
  const labelRef = useRef<HTMLSpanElement>(null);

  const positionCircle = (e: MouseEvent<HTMLElement>) => {
    const el = hostRef.current;
    const circle = circleRef.current;
    if (!el || !circle) return null;
    const rect = el.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    const size = Math.hypot(rect.width, rect.height) * 2.2;
    circle.style.width = `${size}px`;
    circle.style.height = `${size}px`;
    circle.style.left = `${x}px`;
    circle.style.top = `${y}px`;
    return size;
  };

  const handleEnter = (e: MouseEvent<HTMLElement>) => {
    const { gsap } = ensureGsap();
    positionCircle(e);
    gsap.killTweensOf(circleRef.current);
    gsap.set(circleRef.current, { xPercent: -50, yPercent: -50, scale: 0 });
    gsap.to(circleRef.current, { scale: 1, duration: 0.55, ease: "power3.out" });
    if (labelRef.current && hoverTextColor) {
      gsap.to(labelRef.current, { color: hoverTextColor, duration: 0.35, ease: "power2.out" });
    }
    onMouseEnter?.(e as never);
  };

  const handleLeave = (e: MouseEvent<HTMLElement>) => {
    const { gsap } = ensureGsap();
    positionCircle(e);
    gsap.killTweensOf(circleRef.current);
    gsap.to(circleRef.current, { scale: 0, duration: 0.45, ease: "power2.in" });
    if (labelRef.current && textColor) {
      gsap.to(labelRef.current, { color: textColor, duration: 0.35, ease: "power2.out" });
    }
    onMouseLeave?.(e as never);
  };

  return (
    <Comp
      ref={hostRef}
      className={`group relative isolate inline-flex items-center justify-center overflow-hidden ${className}`}
      onMouseEnter={handleEnter}
      onMouseLeave={handleLeave}
      {...rest}
    >
      <span
        ref={circleRef}
        aria-hidden
        className="pointer-events-none absolute rounded-full"
        style={{ background: fillColor, transform: "scale(0)" }}
      />
      <span ref={labelRef} className="relative z-10 inline-flex items-center gap-2" style={{ color: textColor }}>
        {children}
      </span>
    </Comp>
  );
}
