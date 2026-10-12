import { describe, expect, it } from 'vitest'
import { MicError, explain, extensionFor, pickMime } from '@/lib/recorder'

describe('recording format', () => {
  it('prefers Opus in WebM where the browser has it', () => {
    expect(pickMime(() => true)).toBe('audio/webm;codecs=opus')
  })

  it('falls back to MP4 on Safari, which has no WebM recorder', () => {
    expect(pickMime((type) => type === 'audio/mp4')).toBe('audio/mp4')
  })

  it('reports nothing when the browser can record none of them', () => {
    expect(pickMime(() => false)).toBeNull()
  })

  it('names the upload so the server can tell the container', () => {
    expect(extensionFor('audio/webm;codecs=opus')).toBe('webm')
    expect(extensionFor('audio/mp4')).toBe('m4a')
    expect(extensionFor('audio/ogg;codecs=opus')).toBe('ogg')
  })

  it('explains each microphone problem in plain words', () => {
    for (const problem of ['unsupported', 'denied', 'no-device', 'failed'] as const) {
      expect(explain(problem).length).toBeGreaterThan(20)
      expect(new MicError(problem).problem).toBe(problem)
    }
    expect(explain('denied')).toContain('type the dream instead')
  })
})
