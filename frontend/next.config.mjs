/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  experimental: {
    // Required for standalone output in Next.js 16
    serverComponentsExternalPackages: [],
  },
}

export default nextConfig
