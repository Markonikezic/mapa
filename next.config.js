/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'export', // Ovo ISKLJUČUJE server i forsira statički export
  images: {
    unoptimized: true, // Ovo rešava probleme sa slikama tokom build-a
  },
}

module.exports = nextConfig
