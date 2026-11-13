import type { NextConfig } from "next";

const API = process.env.NOVEL_OS_API_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  // The Python API (FastAPI) owns /api; proxy it so the browser stays same-origin.
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API}/api/:path*` }];
  },
};

export default nextConfig;
