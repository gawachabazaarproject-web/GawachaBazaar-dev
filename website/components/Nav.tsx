"use client";

import Image from "next/image";
import { useEffect, useState } from "react";
import RippleButton from "./RippleButton";

const LINKS = [
  { label: "Home", href: "#hero" },
  { label: "Our Story", href: "#story" },
  { label: "Journey", href: "#journey" },
  { label: "Products", href: "#products" },
  { label: "Delivery", href: "#delivery" },
  { label: "Contact", href: "#contact" },
];

export default function Nav() {
  const [scrolled, setScrolled] = useState(false);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 40);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <header
      className={`fixed inset-x-0 top-0 z-50 transition-colors duration-500 ${
        scrolled ? "bg-primary-800/90 backdrop-blur-md shadow-lg shadow-primary-900/20" : "bg-transparent"
      }`}
    >
      <div className="mx-auto flex max-w-7xl items-center justify-between px-5 py-3 sm:px-8">
        <a href="#hero" className="flex items-center gap-3">
          <Image
            src="/images/logo.jpeg"
            alt="Gawacha Bazaar"
            width={44}
            height={44}
            className="h-10 w-10 rounded-full object-cover ring-1 ring-secondary-400/60 sm:h-11 sm:w-11"
            priority
          />
          <span className="hidden flex-col leading-none sm:flex">
            <span className="font-deva text-base font-bold text-secondary-400">गावाचा बाजार</span>
            <span className="mt-0.5 text-[10px] font-semibold uppercase tracking-[0.3em] text-neutral-100/80">
              Gawacha Bazaar
            </span>
          </span>
        </a>

        <nav className="hidden items-center gap-5 xl:flex">
          {LINKS.map((link) => (
            <a
              key={link.href}
              href={link.href}
              className="eyebrow relative whitespace-nowrap text-neutral-100/80 transition-colors hover:text-secondary-400"
            >
              {link.label}
            </a>
          ))}
        </nav>

        <div className="flex items-center gap-4">
          <RippleButton
            as="a"
            href="#app"
            rippleColor="rgba(11,45,32,0.35)"
            className="hidden whitespace-nowrap rounded-full bg-secondary-500 px-5 py-2.5 text-xs font-bold uppercase tracking-widest text-primary-900 transition-transform hover:scale-105 sm:inline-block"
          >
            Get the App
          </RippleButton>
          <button
            aria-label="Toggle menu"
            onClick={() => setOpen((v) => !v)}
            className="flex h-10 w-10 flex-col items-center justify-center gap-1.5 xl:hidden"
          >
            <span
              className={`h-px w-6 bg-neutral-100 transition-transform ${open ? "translate-y-2 rotate-45" : ""}`}
            />
            <span className={`h-px w-6 bg-neutral-100 transition-opacity ${open ? "opacity-0" : ""}`} />
            <span
              className={`h-px w-6 bg-neutral-100 transition-transform ${open ? "-translate-y-2 -rotate-45" : ""}`}
            />
          </button>
        </div>
      </div>

      {open && (
        <div className="absolute inset-x-0 top-full flex flex-col gap-1 bg-primary-800 px-6 py-6 xl:hidden">
          {LINKS.map((link) => (
            <a
              key={link.href}
              href={link.href}
              onClick={() => setOpen(false)}
              className="border-b border-neutral-100/10 py-3 text-sm font-semibold uppercase tracking-widest text-neutral-100/90"
            >
              {link.label}
            </a>
          ))}
          <RippleButton
            as="a"
            href="#app"
            rippleColor="rgba(11,45,32,0.35)"
            onClick={() => setOpen(false)}
            className="mt-4 rounded-full bg-secondary-500 px-5 py-3 text-center text-xs font-bold uppercase tracking-widest text-primary-900"
          >
            Get the App
          </RippleButton>
        </div>
      )}
    </header>
  );
}
