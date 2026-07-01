/** @type {import('next').NextConfig} */
const flyersPort = process.env.FLYERS_PORT || '8010'

const nextConfig = {
  output: 'standalone',
  // Allow the Tailscale Serve hostname in dev (Next.js 15 host check)
  allowedDevOrigins: [
    'setlists.risk-tailor.ts.net',
    '*.risk-tailor.ts.net',
    'bandtools.fly.dev',
    '*.fly.dev',
  ],
  async rewrites() {
    return [
      {
        source: '/flyers',
        destination: `http://127.0.0.1:${flyersPort}/`,
      },
      {
        source: '/flyers/:path*',
        destination: `http://127.0.0.1:${flyersPort}/:path*`,
      },
    ]
  },
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
