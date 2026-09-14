import type { Config } from "tailwindcss";

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
        tertiary: {
          50: "#F2F9F5",
          100: "#E2F1E8",
          200: "#C1E2D0",
          300: "#8FC7AA",
          400: "#5CA985",
          500: "#2E8A64",
          600: "#206F4F",
          700: "#17553D",
          800: "#0F3B2B",
          900: "#071A13",
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
      },
      fontFamily: {
        display: ["var(--font-bodoni)", "serif"],
        script: ["var(--font-instrument)", "serif"],
        sans: ["var(--font-jakarta)", "sans-serif"],
        deva: ["var(--font-baloo)", "sans-serif"],
      },
    },
  },
  plugins: [],
};
export default config;
