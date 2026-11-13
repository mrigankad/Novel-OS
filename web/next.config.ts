import type { NextConfig } from "next";

const API = process.env.NOVEL_OS_API_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  reactStrictMode: true,
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
