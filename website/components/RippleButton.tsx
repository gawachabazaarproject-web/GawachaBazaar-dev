"use client";

import { useRef, type MouseEvent, type ElementType, type ComponentPropsWithoutRef } from "react";

type RippleOwnProps<T extends ElementType> = {
  as?: T;
  rippleColor?: string;
  className?: string;
  children: React.ReactNode;
};

type RippleButtonProps<T extends ElementType> = RippleOwnProps<T> &
  Omit<ComponentPropsWithoutRef<T>, keyof RippleOwnProps<T>>;

export default function RippleButton<T extends ElementType = "button">({
  as,
  rippleColor = "rgba(255,255,255,0.5)",
  className = "",
  children,
  onClick,
  ...rest
}: RippleButtonProps<T>) {
  const Comp = (as || "button") as ElementType;
  const ref = useRef<HTMLElement>(null);

  const handleClick = (e: MouseEvent<HTMLElement>) => {
    const el = ref.current;
    if (el) {
      const rect = el.getBoundingClientRect();
      const size = Math.max(rect.width, rect.height) * 1.8;
      const x = e.clientX - rect.left - size / 2;
      const y = e.clientY - rect.top - size / 2;
      const span = document.createElement("span");
      span.className = "ripple-effect";
      span.style.width = `${size}px`;
      span.style.height = `${size}px`;
      span.style.left = `${x}px`;
      span.style.top = `${y}px`;
      span.style.background = rippleColor;
      el.appendChild(span);
      span.addEventListener("animationend", () => span.remove());
    }
    onClick?.(e as never);
  };

  return (
    <Comp ref={ref} className={`ripple-host ${className}`} onClick={handleClick} {...rest}>
      {children}
    </Comp>
  );
}
