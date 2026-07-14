
/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'export',
  images: {
    unoptimized: true,
  },
  // OVO OBIČNO NE TREBA DA STOJI, OSIM AKO BAŠ NE ZNAŠ ZAŠTO JE TU
  // basePath: '', 
}

module.exports = nextConfig
