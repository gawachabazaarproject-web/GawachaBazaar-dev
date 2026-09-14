"use client";

import Image from "next/image";
import { useState } from "react";
import RippleButton from "./RippleButton";

const LINKS = [
  { label: "Our Story", href: "#story" },
  { label: "The Journey", href: "#journey" },
  { label: "Shop", href: "#products" },
  { label: "Contact", href: "#contact" },
];

export default function Nav() {
  const [open, setOpen] = useState(false);

  return (
    <>
      <header className="pointer-events-none fixed inset-x-0 top-0 z-50">
        <div className="mx-auto flex max-w-[1800px] items-start justify-between px-5 py-5 sm:px-8 sm:py-7">
          <a href="#hero" className="pointer-events-auto flex items-center gap-3">
            <Image
              src="/images/logo.jpeg"
              alt="Gawacha Bazaar"
              width={40}
              height={40}
              className="h-9 w-9 rounded-full object-cover ring-1 ring-neutral-100/30 sm:h-10 sm:w-10"
              priority
            />
            <span className="mix-blend-difference hidden flex-col leading-none text-neutral-100 sm:flex">
              <span className="font-deva text-sm font-bold">गावाचा बाजार</span>
              <span className="mt-1 text-[9px] font-semibold uppercase tracking-widest2">
                Est. Nagpur
              </span>
            </span>
          </a>

          <div className="pointer-events-auto flex items-center gap-8">
            <nav className="mix-blend-difference hidden items-center gap-7 text-neutral-100 lg:flex">
              {LINKS.map((link) => (
                <a
                  key={link.href}
                  href={link.href}
                  className="text-[11px] font-semibold uppercase tracking-widest2 opacity-80 transition-opacity hover:opacity-100"
                >
                  {link.label}
                </a>
              ))}
            </nav>

            <RippleButton
              as="a"
              href="#app"
              fillColor="#D9A52A"
              textColor="#B98624"
              hoverTextColor="#0B2D20"
              className="hidden whitespace-nowrap border border-secondary-500 px-5 py-2.5 text-[11px] font-bold uppercase tracking-widest2 sm:inline-flex"
            >
              Get The App
            </RippleButton>

            <button
              aria-label="Toggle menu"
              onClick={() => setOpen((v) => !v)}
              className="mix-blend-difference flex h-9 w-9 flex-col items-center justify-center gap-1.5 text-neutral-100 lg:hidden"
            >
              <span className={`h-px w-6 bg-current transition-transform ${open ? "translate-y-2 rotate-45" : ""}`} />
              <span className={`h-px w-6 bg-current transition-opacity ${open ? "opacity-0" : ""}`} />
              <span className={`h-px w-6 bg-current transition-transform ${open ? "-translate-y-2 -rotate-45" : ""}`} />
            </button>
          </div>
        </div>
      </header>

      <div
        className={`fixed inset-0 z-40 bg-primary-900 transition-transform duration-700 ease-editorial lg:hidden ${
          open ? "translate-y-0" : "-translate-y-full"
        }`}
      >
        <div className="flex h-full flex-col items-start justify-center gap-2 px-8">
          {LINKS.map((link, i) => (
            <a
              key={link.href}
              href={link.href}
              onClick={() => setOpen(false)}
              className="font-display text-4xl italic text-neutral-100/90 transition-colors hover:text-secondary-400"
              style={{ transitionDelay: `${i * 40}ms` }}
            >
              {link.label}
            </a>
          ))}
          <RippleButton
            as="a"
            href="#app"
            fillColor="#D9A52A"
            textColor="#E4BA55"
            hoverTextColor="#0B2D20"
            onClick={() => setOpen(false)}
            className="mt-10 border border-secondary-500 px-6 py-3 text-xs font-bold uppercase tracking-widest2"
          >
            Get The App
          </RippleButton>
        </div>
      </div>
    </>
  );
}
