import type { NextConfig } from "next";
import path from "path";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  compress: true,
  experimental: {
    optimizeCss: false,
  },
  // Explicit workspace root — required when multiple lockfiles exist
  // so Next.js doesn't incorrectly infer the monorepo root as the project root.
  outputFileTracingRoot: path.resolve(__dirname),
};

export default nextConfig;
