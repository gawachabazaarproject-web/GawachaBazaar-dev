import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// Safe-by-construction headers only - no Content-Security-Policy here.
// Next.js hydration relies on inline scripts, and a strict CSP without
// per-request nonces would need to be verified against every single page
// before shipping; getting that wrong would silently break the entire
// admin panel. Left as a documented follow-up (see the security audit's
// "Remaining Risks" section) rather than guessed at blind.
const securityHeaders = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "no-referrer" },
  { key: "Permissions-Policy", value: "geolocation=(), camera=(), microphone=()" },
];

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  turbopack: {
    root: __dirname,
  },
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }];
  },
};

export default nextConfig;
