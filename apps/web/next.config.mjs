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
    return [
      {
        source: "/((?!api/).*)",
        headers: [
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
