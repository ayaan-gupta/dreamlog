/** Small pure helpers for dates and labels. Everything takes the locale and
 * time zone as arguments so tests do not depend on the machine. */

export function monthKey(iso: string, timeZone = 'UTC'): string {
  const parts = new Intl.DateTimeFormat('en-CA', { year: 'numeric', month: '2-digit', timeZone }).formatToParts(new Date(iso))
  const year = parts.find((p) => p.type === 'year')?.value ?? '0000'
  const month = parts.find((p) => p.type === 'month')?.value ?? '01'
  return `${year}-${month}`
}

export function monthLabel(key: string, locale = 'en-GB'): string {
  const [year, month] = key.split('-').map(Number)
  if (!year || !month) return key
  return new Intl.DateTimeFormat(locale, { month: 'long', year: 'numeric', timeZone: 'UTC' }).format(new Date(Date.UTC(year, month - 1, 1)))
}

export function dayLabel(iso: string, locale = 'en-GB', timeZone?: string): string {
  return new Intl.DateTimeFormat(locale, { weekday: 'short', day: 'numeric', month: 'short', timeZone }).format(new Date(iso))
}

export function clock(totalSeconds: number): string {
  const seconds = Math.max(0, Math.floor(totalSeconds))
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`
}

export function greeting(hour: number): string {
  if (hour >= 4 && hour < 12) return 'Good morning'
  if (hour >= 12 && hour < 18) return 'Good afternoon'
  if (hour >= 18 && hour < 22) return 'Good evening'
  return 'Still up'
}

export function plural(count: number, one: string, many = `${one}s`): string {
  return `${count} ${count === 1 ? one : many}`
}

/** Groups entries, already newest first, by calendar month. */
export function byMonth<T extends { created_at: string }>(entries: T[], timeZone = 'UTC'): { month: string; entries: T[] }[] {
  const groups: { month: string; entries: T[] }[] = []
  for (const entry of entries) {
    const key = monthKey(entry.created_at, timeZone)
    const last = groups[groups.length - 1]
    if (last && last.month === key) last.entries.push(entry)
    else groups.push({ month: key, entries: [entry] })
  }
  return groups
}

const ENGINE_NAMES: Record<string, string> = {
  lexicon: 'the built-in word list',
  procedural: 'the built-in painter',
  fake: 'a test stub',
  hash: 'a test stub',
}

/** "faster-whisper:base.en" becomes "Whisper base.en, on this machine". */
export function engineLabel(engine: string): { name: string; local: boolean } {
  if (engine.startsWith('faster-whisper:')) return { name: `Whisper ${engine.slice(15)}`, local: true }
  if (engine.startsWith('fastembed:')) return { name: engine.slice(10).split('/').pop() ?? engine, local: true }
  if (engine.startsWith('anthropic:')) return { name: `Claude (${engine.slice(10)})`, local: false }
  if (engine.startsWith('api:')) return { name: `image API (${engine.slice(4)})`, local: false }
  return { name: ENGINE_NAMES[engine] ?? engine, local: true }
}

/** What to call a symbol on the dream it came from: the word the dreamer used.
 * A dream about a grandfather should not be labelled "grandmother" because the
 * two were merged into one symbol for counting. */
export function saidAs(symbol: { name: string; surfaces: string[] }): string {
  return symbol.surfaces.length === 0 || symbol.surfaces.includes(symbol.name) ? symbol.name : (symbol.surfaces[0] ?? symbol.name)
}
