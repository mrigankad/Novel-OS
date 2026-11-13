import type { NextConfig } from "next";

const API = process.env.NOVEL_OS_API_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  experimental: { optimizePackageImports: ["lucide-react"] },
  // The FastAPI server owns /api; the browser stays same-origin (no CORS, one port).
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API}/api/:path*` }];
  },
};

export default nextConfig;
