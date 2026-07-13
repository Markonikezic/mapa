/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'export', // Ovo je ono što Next.js traži umesto 'next export' komande
  images: {
    unoptimized: true,
  },
}

module.exports = nextConfig
