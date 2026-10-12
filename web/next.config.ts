import type { NextConfig } from 'next'

const api = process.env.DREAMLOG_API_URL ?? `http://127.0.0.1:${process.env.API_PORT ?? '8104'}`

const config: NextConfig = {
  reactStrictMode: true,
  devIndicators: false,
  // The browser only ever talks to this origin. Everything under /api is passed
  // straight through to the FastAPI service, so there is no CORS and no API
  // address baked into the client bundle.
  async rewrites() {
    return [{ source: '/api/:path*', destination: `${api}/api/:path*` }]
  },
  async headers() {
    return [{ source: '/sw.js', headers: [{ key: 'Cache-Control', value: 'no-cache' }] }]
  },
}

export default config
