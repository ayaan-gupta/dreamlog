import type { MetadataRoute } from 'next'

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: 'Dreamlog',
    short_name: 'Dreamlog',
    description: 'A private, visual dream journal.',
    start_url: '/',
    display: 'standalone',
    orientation: 'portrait',
    background_color: '#f4f2ec',
    theme_color: '#f4f2ec',
    icons: [
      { src: '/art/icon-192.png', sizes: '192x192', type: 'image/png', purpose: 'any' },
      { src: '/art/icon-512.png', sizes: '512x512', type: 'image/png', purpose: 'any' },
      { src: '/art/icon-maskable.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
    ],
  }
}
