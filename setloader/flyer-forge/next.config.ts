import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  basePath: "/flyer-forge",
  assetPrefix: "/flyer-forge",
  cacheComponents: true,
  partialPrefetching: true,
  serverExternalPackages: ["@electric-sql/pglite"],
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "same-origin" },
          { key: "Content-Security-Policy", value: "object-src 'none'; base-uri 'self'; form-action 'self'" },
        ],
      },
      {
        source: "/api/:path*",
        headers: [{ key: "Content-Security-Policy", value: "default-src 'none'; sandbox" }],
      },
    ];
  },
  turbopack: {
    resolveAlias: {
      "./identity.dev.js": "./cursor/identity.dev.ts",
    },
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
