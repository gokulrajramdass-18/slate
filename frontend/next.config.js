/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: 'standalone',
  serverExternalPackages: [],
  async rewrites() {
    // In Kubernetes, use the internal service URL
    // This is set at runtime via environment variable
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5055';
    console.log('API URL configured:', apiUrl);
    return [
      {
        source: '/api/:path*',
        destination: `${apiUrl}/api/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
