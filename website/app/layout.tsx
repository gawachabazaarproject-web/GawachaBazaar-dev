import type { Metadata } from "next";
import { Bodoni_Moda, Instrument_Serif, Plus_Jakarta_Sans, Baloo_2 } from "next/font/google";
import "./globals.css";

const bodoni = Bodoni_Moda({
  subsets: ["latin"],
  variable: "--font-bodoni",
  weight: ["400", "500", "600", "700", "800", "900"],
  style: ["normal", "italic"],
  display: "swap",
});

const instrument = Instrument_Serif({
  subsets: ["latin"],
  variable: "--font-instrument",
  weight: ["400"],
  style: ["italic", "normal"],
  display: "swap",
});

const jakarta = Plus_Jakarta_Sans({
  subsets: ["latin"],
  variable: "--font-jakarta",
  weight: ["400", "500", "600", "700", "800"],
  display: "swap",
});

const baloo = Baloo_2({
  subsets: ["devanagari", "latin"],
  variable: "--font-baloo",
  weight: ["500", "600", "700", "800"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "Gawacha Bazaar | Village Fresh, Straight to Nagpur",
  description:
    "Gawacha Bazaar connects Nagpur households directly to family farms across Maharashtra — fresh, hand-graded produce delivered daily, with zero middlemen.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body
        className={`${bodoni.variable} ${instrument.variable} ${jakarta.variable} ${baloo.variable} font-sans bg-neutral-100 text-primary-900 antialiased`}
      >
        {children}
      </body>
    </html>
  );
}
