'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import type { ReactNode } from 'react'
import { useEffect } from 'react'
import { AtlasIcon, LockIcon, MicIcon, PatternsIcon, SearchIcon, TimelineIcon } from './icons'

const TABS = [
  { href: '/', label: 'Record', icon: MicIcon },
  { href: '/timeline', label: 'Timeline', icon: TimelineIcon },
  { href: '/patterns', label: 'Patterns', icon: PatternsIcon },
  { href: '/atlas', label: 'Atlas', icon: AtlasIcon },
  { href: '/search', label: 'Search', icon: SearchIcon },
] as const

function isCurrent(pathname: string, href: string): boolean {
  if (href === '/') return pathname === '/'
  if (href === '/timeline') return pathname.startsWith('/timeline') || pathname.startsWith('/entry')
  return pathname.startsWith(href)
}

export function Shell({ children }: { children: ReactNode }) {
  const pathname = usePathname()

  useEffect(() => {
    // The service worker only caches the app shell. See public/sw.js.
    if ('serviceWorker' in navigator && process.env.NODE_ENV === 'production') {
      void navigator.serviceWorker.register('/sw.js')
    }
  }, [])

  return (
    <>
      <header className="top">
        <Link href="/" className="brand">
          <img src="/art/logo.png" alt="" width={28} height={28} />
          Dreamlog
        </Link>
        <nav aria-label="Sections">
          {TABS.map((tab) => (
            <Link key={tab.href} href={tab.href} aria-current={isCurrent(pathname, tab.href) ? 'page' : undefined}>
              {tab.label}
            </Link>
          ))}
        </nav>
        <Link href="/privacy" className="icon-button" aria-label="Privacy and data" aria-current={pathname.startsWith('/privacy') ? 'page' : undefined}>
          <LockIcon size={20} />
        </Link>
      </header>
      {children}
      <nav className="tabs" aria-label="Sections">
        {TABS.map((tab) => (
          <Link key={tab.href} href={tab.href} aria-current={isCurrent(pathname, tab.href) ? 'page' : undefined}>
            <tab.icon size={23} />
            {tab.label}
          </Link>
        ))}
      </nav>
    </>
  )
}
