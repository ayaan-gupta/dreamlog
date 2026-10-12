import { describe, expect, it } from 'vitest'
import { byMonth, clock, dayLabel, engineLabel, greeting, monthKey, monthLabel, plural, saidAs } from '@/lib/format'

describe('dates and labels', () => {
  it('groups entries by calendar month in the given time zone', () => {
    const entries = [
      { id: 'c', created_at: '2026-10-01T03:30:00Z' },
      { id: 'b', created_at: '2026-09-30T23:30:00Z' },
      { id: 'a', created_at: '2026-09-02T06:40:00Z' },
    ]
    expect(byMonth(entries, 'UTC').map((g) => [g.month, g.entries.map((e) => e.id)])).toEqual([
      ['2026-10', ['c']],
      ['2026-09', ['b', 'a']],
    ])
    // Half past three in the morning UTC is still September in Chicago.
    expect(byMonth(entries, 'America/Chicago').map((g) => g.month)).toEqual(['2026-09'])
    expect(byMonth([], 'UTC')).toEqual([])
  })

  it('names months and days', () => {
    expect(monthKey('2026-05-03T06:40:00Z')).toBe('2026-05')
    expect(monthLabel('2026-05')).toBe('May 2026')
    expect(monthLabel('nonsense')).toBe('nonsense')
    expect(dayLabel('2026-10-10T06:40:00Z', 'en-GB', 'UTC')).toBe('Sat 10 Oct')
  })

  it('formats a running clock', () => {
    expect(clock(0)).toBe('0:00')
    expect(clock(61.9)).toBe('1:01')
    expect(clock(-3)).toBe('0:00')
  })

  it('greets by the hour', () => {
    expect([5, 13, 19, 2].map(greeting)).toEqual(['Good morning', 'Good afternoon', 'Good evening', 'Still up'])
  })

  it('counts in English', () => {
    expect(plural(1, 'dream')).toBe('1 dream')
    expect(plural(0, 'dream')).toBe('0 dreams')
    expect(plural(2, 'person', 'people')).toBe('2 people')
  })

  it('labels a symbol on its own dream with the word that was said', () => {
    expect(saidAs({ name: 'grandmother', surfaces: ['grandfather'] })).toBe('grandfather')
    expect(saidAs({ name: 'water', surfaces: ['ocean', 'water'] })).toBe('water')
    expect(saidAs({ name: 'door', surfaces: [] })).toBe('door')
  })

  it('says which engines run on this machine and which do not', () => {
    expect(engineLabel('faster-whisper:base.en')).toEqual({ name: 'Whisper base.en', local: true })
    expect(engineLabel('fastembed:sentence-transformers/all-MiniLM-L6-v2')).toEqual({ name: 'all-MiniLM-L6-v2', local: true })
    expect(engineLabel('lexicon').local).toBe(true)
    expect(engineLabel('anthropic:claude-sonnet-5-5')).toEqual({ name: 'Claude (claude-sonnet-5-5)', local: false })
    expect(engineLabel('api:gpt-image-1').local).toBe(false)
  })
})
