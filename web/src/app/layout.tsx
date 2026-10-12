import type { Metadata, Viewport } from 'next'
import type { ReactNode } from 'react'
import { Shell } from '@/components/shell'
import './globals.css'

export const metadata: Metadata = {
  title: 'Dreamlog',
  description: 'Dictate a dream on waking, get an illustration of it, and see which symbols keep coming back.',
  applicationName: 'Dreamlog',
  appleWebApp: { capable: true, title: 'Dreamlog', statusBarStyle: 'default' },
  icons: { icon: '/art/icon-192.png', apple: '/art/icon-192.png' },
  robots: { index: false, follow: false },
}

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  viewportFit: 'cover',
  themeColor: [
    { media: '(prefers-color-scheme: light)', color: '#f4f2ec' },
    { media: '(prefers-color-scheme: dark)', color: '#121116' },
  ],
}

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Shell>{children}</Shell>
      </body>
    </html>
  )
}
