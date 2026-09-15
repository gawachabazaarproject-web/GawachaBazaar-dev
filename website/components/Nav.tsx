"use client";

import Image from "next/image";
import { useEffect, useState } from "react";
import RippleButton from "./RippleButton";

const LINKS = [
  { label: "Our Story", href: "#story" },
  { label: "The Journey", href: "#journey" },
  { label: "Shop", href: "#products" },
  { label: "Contact", href: "#contact" },
];

// Roughly the header's own height - the IntersectionObserver's rootMargin
// below carves out a thin horizontal band at this offset from the top of
// the viewport, so a section only counts as "active" once its own
// background is genuinely what's rendered directly behind the fixed nav.
const NAV_HEIGHT_PX = 88;

type Theme = "light" | "dark";

export default function Nav() {
  const [open, setOpen] = useState(false);
  // Every section on the page is dark (bg-primary-900/800 or bg-tertiary-800)
  // except a handful of cream (bg-neutral-100) ones - see each section's
  // `data-nav-theme` attribute. The hero at the very top is dark, so that's
  // the correct initial value before the observer below has fired once.
  const [theme, setTheme] = useState<Theme>("dark");

  useEffect(() => {
    const sections = Array.from(document.querySelectorAll<HTMLElement>("[data-nav-theme]"));
    if (sections.length === 0) return;

    // Carves a 1px-tall detection line out of the viewport, exactly
    // NAV_HEIGHT_PX from the top - a section only reports as intersecting
    // once its own box actually spans that line, i.e. once its background
    // is genuinely what's rendered directly behind the fixed nav (not
    // merely "somewhere in the upper portion of the screen").
    const bottomMargin = Math.max(window.innerHeight - NAV_HEIGHT_PX - 1, 0);
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            const next = (entry.target as HTMLElement).dataset.navTheme as Theme | undefined;
            if (next) setTheme(next);
          }
        }
      },
      { rootMargin: `-${NAV_HEIGHT_PX}px 0px -${bottomMargin}px 0px`, threshold: 0 },
    );
    sections.forEach((section) => observer.observe(section));
    return () => observer.disconnect();
  }, []);

  const isLight = theme === "light";
  // No background/blur on the header itself - legibility comes from these
  // text/icon colors actually matching (or contrasting against) whatever
  // section is behind the nav, not from a translucent panel sitting on
  // top of it.
  const textClass = isLight ? "text-primary-800" : "text-neutral-100";

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
              className={`h-9 w-9 rounded-full object-cover ring-1 sm:h-10 sm:w-10 ${
                isLight ? "ring-primary-800/20" : "ring-neutral-100/30"
              }`}
              priority
            />
            <span className={`hidden flex-col leading-none transition-colors duration-300 sm:flex ${textClass}`}>
              <span className="font-deva text-sm font-bold">गावाचा बाजार</span>
              <span className="mt-1 text-[9px] font-semibold uppercase tracking-widest2">
                Est. Nagpur
              </span>
            </span>
          </a>

          <div className="pointer-events-auto flex items-center gap-8">
            <nav className={`hidden items-center gap-7 transition-colors duration-300 lg:flex ${textClass}`}>
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
              fillColor={isLight ? "#0B2D20" : "#D9A52A"}
              textColor={isLight ? "#0B2D20" : "#B98624"}
              hoverTextColor={isLight ? "#F1F8F4" : "#0B2D20"}
              className={`hidden whitespace-nowrap border px-5 py-2.5 text-[11px] font-bold uppercase tracking-widest2 transition-colors duration-300 sm:inline-flex ${
                isLight ? "border-primary-800" : "border-secondary-500"
              }`}
            >
              Get The App
            </RippleButton>

            <button
              aria-label="Toggle menu"
              onClick={() => setOpen((v) => !v)}
              className={`flex h-9 w-9 flex-col items-center justify-center gap-1.5 transition-colors duration-300 lg:hidden ${textClass}`}
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
