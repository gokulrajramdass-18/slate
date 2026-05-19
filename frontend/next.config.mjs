/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  experimental: {
    // Required for standalone output in Next.js 16
    serverComponentsExternalPackages: [],
  },
  // Force cache bust
  generateBuildId: async () => {
    return `build-${Date.now()}`
  },
  // Disable caching for HTML pages
  async headers() {
    return [
      {
        source: '/:path*',
        headers: [
          {
            key: 'Cache-Control',
            value: 'no-store, no-cache, must-revalidate, proxy-revalidate, max-age=0',
          },
        ],
      },
    ]
  },
}

export default nextConfig
