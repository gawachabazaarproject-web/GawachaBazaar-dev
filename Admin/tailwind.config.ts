import type { Config } from "tailwindcss";

/**
 * Shares its brand palette and type scale verbatim with website/tailwind.config.ts
 * and mobile/src/theme/colors.ts - same primary/secondary/neutral/earth hues,
 * same three type families, same status-color hex values - so the admin panel
 * reads as the same product's backstage, not a different app wearing similar
 * colors. `status.*` below is copied 1:1 from mobile/src/theme/colors.ts so a
 * "danger" state means the same red everywhere a Gawacha Bazaar surface shows one.
 */
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        primary: {
          50: "#F1F8F4",
          100: "#DCEEE3",
          200: "#B3D6C1",
          300: "#7FB496",
          400: "#4F9270",
          500: "#2C7350",
          600: "#1B5C3F",
          700: "#12442F",
          800: "#0B2D20",
          900: "#05130D",
        },
        secondary: {
          50: "#FDF8EE",
          100: "#FAF0D9",
          200: "#F5E2B3",
          300: "#EDCE85",
          400: "#E4BA55",
          500: "#D9A52A",
          600: "#B98624",
          700: "#93661A",
          800: "#6B4A10",
          900: "#3D2B08",
        },
        neutral: {
          50: "#FCFBF7",
          100: "#F7F4EB",
          200: "#EDE7D6",
          300: "#DCD3B8",
          400: "#B9AD8A",
          500: "#8F8362",
          600: "#6B6249",
          700: "#4A4433",
          800: "#2E2A20",
          900: "#16140F",
        },
        earth: {
          50: "#FBF3EC",
          100: "#F3E1D2",
          200: "#E4C0A4",
          300: "#D19E76",
          400: "#BD7F55",
          500: "#A65D43",
          600: "#8B4A36",
          700: "#6E3B2C",
          800: "#4F2C22",
          900: "#301B15",
        },
        charcoal: {
          DEFAULT: "#1B1B18",
          light: "#2A2A25",
        },
        status: {
          success: "#1E8E5A",
          successLight: "#E5F4EC",
          warning: "#C9821A",
          warningLight: "#FBF0DE",
          danger: "#BA1A1A",
          dangerLight: "#FFDAD6",
          info: "#2E6FBB",
          infoLight: "#E9F1FA",
        },
      },
      fontFamily: {
        display: ["var(--font-bodoni)", "serif"],
        script: ["var(--font-instrument)", "serif"],
        sans: ["var(--font-jakarta)", "sans-serif"],
      },
      letterSpacing: {
        widest2: "0.22em",
      },
    },
  },
  plugins: [],
};
export default config;
