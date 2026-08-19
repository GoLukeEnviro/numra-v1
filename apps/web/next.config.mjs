/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Minimal, self-contained runtime image for docker/web.Dockerfile.
  output: "standalone",
  eslint: {
    // Linting is run separately via `pnpm web:lint`; don't block `next build` on it
    // so CI can report lint and build failures independently.
    ignoreDuringBuilds: true,
  },

  // The same-origin API proxy itself is NOT implemented here via rewrites(): that
  // async function is evaluated once at `next build` time and baked into
  // .next/routes-manifest.json, so an env var read there would not actually be
  // reconfigurable at container start — see src/app/api/[...path]/route.ts's
  // docstring for the Route Handler that replaces it (and genuinely reads
  // API_INTERNAL_URL per-request).
  async headers() {
    // No nonce/strict-dynamic: verified against a real headless-Chromium load
    // (see specs/evidence) that Next.js 14's own inline hydration/RSC bootstrap
    // scripts do NOT automatically pick up a middleware-set CSP nonce the way the
    // App Router docs describe for a later Next.js version — a nonce+strict-dynamic
    // policy blocked every script on the page, including the framework's own,
    // breaking hydration entirely. `script-src 'self'` (no 'unsafe-inline') still
    // blocks any externally-hosted or attacker-injected <script src="..."> from a
    // different origin, which is the CSP protection that matters most here; inline
    // scripts are exclusively Next.js's own generated bootstrap payload, never
    // user-controlled content (React already escapes all rendered data).
    const csp = [
      "default-src 'self'",
      "script-src 'self' 'unsafe-inline'",
      "style-src 'self' 'unsafe-inline'",
      "img-src 'self' data:",
      "font-src 'self'",
      "object-src 'none'",
      "base-uri 'self'",
      "form-action 'self'",
      "frame-ancestors 'none'",
      "connect-src 'self'",
    ].join("; ");
    return [
      {
        source: "/((?!api/).*)",
        headers: [
          { key: "Content-Security-Policy", value: csp },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          {
            key: "Permissions-Policy",
            value: "camera=(), microphone=(), geolocation=(), payment=()",
          },
        ],
      },
    ];
  },
};

export default nextConfig;
