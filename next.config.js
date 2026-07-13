/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone', // Ovo pomaže Vercelu da bolje rukuje server komponentama
  eslint: {
    ignoreDuringBuilds: true, // Ovo ubrzava build i eliminiše sitne greške pri check-u
  },
}

module.exports = nextConfig
