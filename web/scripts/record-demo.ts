/**
 * Records docs/demo.gif by driving the real app in a headless browser.
 *
 *   make dev          (in one terminal)
 *   make demo         (in another)
 *
 * Nothing in the recording is staged. The browser is given a fake microphone
 * that plays api/tests/fixtures/clip-demo.m4a (synthetic speech), the page
 * records it with MediaRecorder exactly as it would a person, and the server
 * transcribes it with Whisper and paints the picture. The 30 sample dreams
 * are loaded first so the timeline, graph and atlas have something in them.
 *
 * RESET=1 wipes the database before starting. Without it the samples are
 * added to whatever is there.
 */
import { execFileSync } from 'node:child_process'
import { mkdtempSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import path from 'node:path'
import sharp from 'sharp'
import { BASE, launch } from './lib/browser'
import type { Frame } from './lib/gif'
import { encodeGif } from './lib/gif'

const WIDTH = 390
const HEIGHT = 760
const ROOT = path.join(process.cwd(), '..')

async function ensureSamples() {
  if (process.env.RESET === '1') await fetch(`${BASE}/api/all?confirm=delete-everything`, { method: 'DELETE' })
  await fetch(`${BASE}/api/fixtures/load`, { method: 'POST' })
  for (;;) {
    const status = (await (await fetch(`${BASE}/api/fixtures/status`)).json()) as { running: boolean; error: string | null }
    if (status.error) throw new Error(`loading samples failed: ${status.error}`)
    if (!status.running) return
    await new Promise((resolve) => setTimeout(resolve, 500))
  }
}

async function main() {
  await ensureSamples()
  const wav = path.join(mkdtempSync(path.join(tmpdir(), 'dreamlog-demo-')), 'mic.wav')
  execFileSync(path.join(ROOT, '.venv', 'bin', 'python'), [path.join(ROOT, 'scripts', 'to_wav.py'), path.join(ROOT, 'api', 'tests', 'fixtures', 'clip-demo.m4a'), wav, '30'])

  const browser = await launch({
    args: ['--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream', `--use-file-for-fake-audio-capture=${wav}%noloop`],
  })
  const context = await browser.newContext({ viewport: { width: WIDTH, height: HEIGHT }, deviceScaleFactor: 1, isMobile: true, hasTouch: true })
  await context.grantPermissions(['microphone'], { origin: BASE })
  const page = await context.newPage()
  const frames: Frame[] = []

  const shoot = async (delay: number) => {
    const png = await page.screenshot({ type: 'png' })
    const { data } = await sharp(png).ensureAlpha().raw().toBuffer({ resolveWithObject: true })
    frames.push({ rgba: new Uint8Array(data), delay })
  }
  const hold = async (ms: number, every = 220, shown = every) => {
    for (let t = 0; t < ms; t += every) {
      await shoot(shown)
      await page.waitForTimeout(every)
    }
  }

  // Record.
  await page.goto(BASE, { waitUntil: 'networkidle' })
  await hold(1400)
  await page.getByRole('button', { name: 'Start recording' }).tap()
  await hold(12_500, 300, 110) // headless Chromium feeds the fake microphone slower than real time, so wait well past the clip's 10 seconds
  await page.getByRole('button', { name: 'Stop recording and save' }).tap()
  const stopped = Date.now()
  await hold(600)
  await page.waitForURL('**/entry/**', { timeout: 60_000 })
  await page.waitForFunction(() => document.querySelector<HTMLImageElement>('img.picture')?.complete === true)
  console.log(`stop to saved entry on screen: ${((Date.now() - stopped) / 1000).toFixed(1)} s`)
  await hold(2400)
  await page.evaluate(() => window.scrollTo({ top: 430, behavior: 'instant' as ScrollBehavior }))
  await hold(2600)
  await page.getByRole('button', { name: 'Keep it' }).tap()
  await hold(700)
  await page.evaluate(() => window.scrollTo({ top: 620, behavior: 'instant' as ScrollBehavior }))
  await hold(1600)

  // Timeline.
  await page.getByRole('navigation', { name: 'Sections' }).last().getByRole('link', { name: 'Timeline' }).tap()
  await page.waitForLoadState('networkidle')
  await hold(1500)
  await page.evaluate(() => window.scrollTo({ top: 520, behavior: 'instant' as ScrollBehavior }))
  await hold(1500)

  // Patterns: pick the water symbol.
  await page.getByRole('navigation', { name: 'Sections' }).last().getByRole('link', { name: 'Patterns' }).tap()
  await page.waitForSelector('.graph circle')
  await page.evaluate(() => window.scrollTo({ top: 250, behavior: 'instant' as ScrollBehavior }))
  await hold(1600)
  const water = page.locator('.graph g', { has: page.locator('text', { hasText: /^water$/ }) }).locator('circle')
  await water.first().dispatchEvent('click')
  await hold(2200)
  await page.evaluate(() => window.scrollTo({ top: 760, behavior: 'instant' as ScrollBehavior }))
  await hold(1800)

  // Search.
  await page.getByRole('navigation', { name: 'Sections' }).last().getByRole('link', { name: 'Search' }).tap()
  await page.waitForLoadState('networkidle')
  await page.getByRole('textbox', { name: 'Search your dreams' }).tap()
  for (const char of 'being chased') {
    await page.keyboard.type(char)
    await shoot(80)
  }
  await page.keyboard.press('Enter')
  await page.waitForSelector('.score')
  await hold(2600)

  // Atlas.
  await page.getByRole('navigation', { name: 'Sections' }).last().getByRole('link', { name: 'Atlas' }).tap()
  await page.waitForFunction(() => document.querySelector<HTMLImageElement>('img.poster')?.complete === true, null, { timeout: 60_000 })
  await hold(2800)

  await browser.close()
  const gif = encodeGif(frames, WIDTH, HEIGHT)
  const out = path.join(ROOT, 'docs', 'demo.gif')
  writeFileSync(out, gif)
  console.log(`${frames.length} frames, ${(gif.length / 1024 / 1024).toFixed(2)} MB -> ${out}`)
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})
