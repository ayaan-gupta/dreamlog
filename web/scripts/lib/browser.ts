import { existsSync, readdirSync } from 'node:fs'
import { homedir } from 'node:os'
import path from 'node:path'
import type { Browser, LaunchOptions } from 'playwright'
import { chromium } from 'playwright'

/** Reuses whatever Chromium Playwright has already downloaded, any revision. */
export function cachedChromium(): string | undefined {
  const cache = path.join(homedir(), 'Library', 'Caches', 'ms-playwright')
  if (!existsSync(cache)) return undefined
  for (const dir of readdirSync(cache)
    .filter((d) => d.startsWith('chromium_headless_shell-'))
    .sort()
    .reverse()) {
    for (const arch of ['chrome-headless-shell-mac-arm64', 'chrome-mac', 'chrome-headless-shell-mac-x64']) {
      const bin = path.join(cache, dir, arch, 'chrome-headless-shell')
      if (existsSync(bin)) return bin
    }
  }
  return undefined
}

export function launch(options: LaunchOptions = {}): Promise<Browser> {
  return chromium.launch({ executablePath: cachedChromium(), ...options })
}

export const BASE = process.env.DEMO_URL ?? `http://localhost:${process.env.WEB_PORT ?? '4104'}`
