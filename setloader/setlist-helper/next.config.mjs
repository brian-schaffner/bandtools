/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  // Allow the Tailscale Serve hostname in dev (Next.js 15 host check)
  allowedDevOrigins: [
    'setlists.risk-tailor.ts.net',
    '*.risk-tailor.ts.net',
    'bandtools.fly.dev',
    '*.fly.dev',
  ],
  eslint: {
    ignoreDuringBuilds: true,
  },
  typescript: {
    ignoreBuildErrors: true,
  },
  images: {
    unoptimized: true,
  },
}

export default nextConfig
