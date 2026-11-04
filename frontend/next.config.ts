import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  experimental: {
    // A geracao por IA pode exceder os 30 segundos padrao do proxy.
    proxyTimeout: 240_000,
  },
  async rewrites() {
    const apiUrl = (
      process.env.API_URL ||
      process.env.NEXT_PUBLIC_API_URL ||
      'http://localhost:8000'
    ).replace(/\/+$/, '');

    return [
      {
        source: '/api/:path*',
        destination: `${apiUrl}/:path*`,
      },
    ];
  },
};

export default nextConfig;
