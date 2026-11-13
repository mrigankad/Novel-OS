import type { NextConfig } from "next";

const API = process.env.NOVEL_OS_API_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // Separate output dirs so `next build` never clobbers a running `next dev`.
  distDir: process.env.NODE_ENV === "production" ? ".next-prod" : ".next",
  // Self-contained server bundle (.next-prod/standalone/server.js) for the Docker image.
  // Rewrites still work; their destination is fixed at build time from NOVEL_OS_API_URL.
  output: "standalone",
  // Trace from web/ itself, so a lockfile in a parent folder can't nest server.js deep inside.
  outputFileTracingRoot: process.cwd(),
  poweredByHeader: false,
  // Off on purpose: Next would gzip the proxied SSE stream (/api/.../events) and buffer it.
  // FastAPI already gzips API responses; put a CDN or reverse proxy in front for static assets.
  compress: false,
  experimental: { optimizePackageImports: ["lucide-react"] },
  // The FastAPI server owns /api; the browser stays same-origin (no CORS, one port).
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API}/api/:path*` }];
  },
};

export default nextConfig;
