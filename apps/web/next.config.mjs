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
};

export default nextConfig;
