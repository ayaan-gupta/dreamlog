/**
 * Screenshots of the running app, for docs/ and for checking the layout.
 *
 *   make dev            (in one terminal, with the sample dreams loaded)
 *   make shots          (in another)
 *
 * OUT=<dir> writes somewhere other than docs/. ONLY=<name> takes one page.
 * ALL=1 takes every page at both widths, SCHEME=dark uses the dark theme.
 */
import { mkdirSync } from 'node:fs'
import path from 'node:path'
import type { Page } from 'playwright'
import { BASE, launch } from './lib/browser'

const OUT = process.env.OUT ?? path.join(process.cwd(), '..', 'docs')
const ONLY = process.env.ONLY

interface Shot {
  name: string
  url: string
  /** Which widths go into docs/. ALL=1 takes both for every page. */
  docs: ('desktop' | 'phone')[]
  prepare?: (page: Page) => Promise<void>
}

async function firstEntryWith(text: string): Promise<string> {
  const entries = (await (await fetch(`${BASE}/api/entries`)).json()) as { id: string; transcript: string }[]
  const hit = entries.find((entry) => entry.transcript.includes(text)) ?? entries[0]
  if (!hit) throw new Error('no entries: load the sample dreams first')
  return hit.id
}

async function symbolId(name: string): Promise<number> {
  const graph = (await (await fetch(`${BASE}/api/graph`)).json()) as { nodes: { id: number; name: string }[] }
  return graph.nodes.find((node) => node.name === name)?.id ?? graph.nodes[0]?.id ?? 0
}

async function main() {
  mkdirSync(OUT, { recursive: true })
  const entry = await firstEntryWith(process.env.ENTRY ?? 'walking along a beach')
  const water = await symbolId('water')
  const shots: Shot[] = [
    { name: 'record', url: '/', docs: ['phone'] },
    { name: 'timeline', url: '/timeline', docs: ['phone'] },
    { name: 'entry', url: `/entry/${entry}`, docs: ['desktop'] },
    { name: 'patterns', url: `/patterns?symbol=${water}`, docs: ['desktop'] },
    { name: 'search', url: '/search?q=being%20chased', docs: ['desktop'] },
    {
      name: 'atlas',
      url: '/atlas',
      docs: ['desktop'],
      prepare: async (page) => {
        await page.getByRole('button', { name: 'September 2026' }).click()
        await page.waitForFunction(() => {
          const poster = document.querySelector<HTMLImageElement>('img.poster')
          return poster?.complete === true && poster.style.opacity === '1'
        }, null, { timeout: 60_000 })
      },
    },
    { name: 'privacy', url: '/privacy', docs: ['phone'] },
  ]
  const browser = await launch()
  for (const device of [
    { tag: 'desktop', viewport: { width: 1280, height: 860 }, deviceScaleFactor: 1 },
    { tag: 'phone', viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true },
  ]) {
    const context = await browser.newContext({ ...device, colorScheme: process.env.SCHEME === 'dark' ? 'dark' : 'light' })
    const page = await context.newPage()
    for (const shot of shots) {
      if (ONLY && shot.name !== ONLY) continue
      if (!process.env.ALL && !shot.docs.includes(device.tag as 'desktop' | 'phone')) continue
      await page.goto(BASE + shot.url, { waitUntil: 'networkidle' })
      await shot.prepare?.(page)
      await page.waitForTimeout(500)
      const file = path.join(OUT, `${shot.name}-${device.tag}${process.env.SCHEME === 'dark' ? '-dark' : ''}.png`)
      await page.screenshot({ path: file })
      console.log(file)
    }
    await context.close()
  }
  await browser.close()
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})
