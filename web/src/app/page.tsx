'use client'

import { useRouter } from 'next/navigation'
import { useCallback, useEffect, useRef, useState } from 'react'
import { EntryRow, ErrorNote, useLoad } from '@/components/bits'
import { LockIcon, MicIcon, StopIcon } from '@/components/icons'
import { api } from '@/lib/api'
import { clock, greeting } from '@/lib/format'
import { MicError, Recorder, explain, extensionFor } from '@/lib/recorder'

type Phase = 'idle' | 'recording' | 'working' | 'typing'

const STEPS = [
  { art: 'onboarding-record', title: 'Say it', text: 'One tap, then talk. Fragments are fine.' },
  { art: 'onboarding-picture', title: 'See it', text: 'Each dream gets its own watercolour.' },
  { art: 'onboarding-patterns', title: 'Notice it', text: 'Over months, see which symbols return.' },
]

export default function RecordPage() {
  const router = useRouter()
  const [phase, setPhase] = useState<Phase>('idle')
  const [seconds, setSeconds] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [text, setText] = useState('')
  const [hello, setHello] = useState('Good morning')
  const recorder = useRef<Recorder | null>(null)
  const halo = useRef<HTMLSpanElement | null>(null)
  const { data: entries } = useLoad(() => api.entries())
  const { data: privacy } = useLoad(() => api.privacy())

  useEffect(() => setHello(greeting(new Date().getHours())), [])
  useEffect(() => () => recorder.current?.cancel(), [])

  useEffect(() => {
    if (phase !== 'recording') return
    let frame = 0
    const tick = () => {
      const active = recorder.current
      if (active) {
        setSeconds(active.seconds())
        if (halo.current) halo.current.style.transform = `scale(${1 + active.level() * 0.42})`
      }
      frame = requestAnimationFrame(tick)
    }
    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [phase])

  const start = useCallback(async () => {
    setError(null)
    const next = new Recorder()
    try {
      await next.start()
      recorder.current = next
      setSeconds(0)
      setPhase('recording')
    } catch (reason) {
      setError(explain(reason instanceof MicError ? reason.problem : 'failed'))
    }
  }, [])

  const stop = useCallback(async () => {
    const active = recorder.current
    if (!active) return
    setPhase('working')
    if (halo.current) halo.current.style.transform = ''
    try {
      const recording = await active.stop()
      recorder.current = null
      const entry = await api.createFromAudio(recording.blob, `dream.${extensionFor(recording.mime)}`)
      if (entry.timings_ms?.total) sessionStorage.setItem(`saved-in:${entry.id}`, String(entry.timings_ms.total))
      router.push(`/entry/${entry.id}?new=1`)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'That recording could not be saved.')
      setPhase('idle')
    }
  }, [router])

  const saveText = useCallback(async () => {
    setError(null)
    setPhase('working')
    try {
      const entry = await api.createFromText(text)
      router.push(`/entry/${entry.id}?new=1`)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'That could not be saved.')
      setPhase('typing')
    }
  }, [router, text])

  const latest = entries?.[0]
  const audioPromise = privacy?.keep_audio ? 'Audio is kept, encrypted.' : 'Audio is deleted once it is transcribed.'

  return (
    <main className="record-page">
      <h1 className="title">{hello}.</h1>
      <p className="lede">Say what you remember before it goes.</p>

      {phase === 'typing' ? (
        <div style={{ width: '100%', marginTop: 28, textAlign: 'left' }}>
          <textarea
            className="sheet"
            value={text}
            onChange={(event) => setText(event.target.value)}
            placeholder="I was back in my grandmother's house, but the staircase kept going up..."
            aria-label="Your dream"
            autoFocus
          />
          <div className="actions" style={{ marginTop: 14 }}>
            <button className="button" onClick={saveText} disabled={text.trim().length < 3}>
              Save dream
            </button>
            <button className="button quiet" onClick={() => setPhase('idle')}>
              Record instead
            </button>
          </div>
        </div>
      ) : (
        <>
          <div className="record-wrap">
            <span className="halo" ref={halo} />
            {phase === 'idle' && (
              <button className="record" data-state="idle" onClick={start} aria-label="Start recording">
                <MicIcon size={56} strokeWidth={1.5} />
              </button>
            )}
            {phase === 'recording' && (
              <button className="record" data-state="recording" onClick={stop} aria-label="Stop recording and save">
                <StopIcon size={64} />
              </button>
            )}
            {phase === 'working' && (
              <span className="record" data-state="working" role="status" aria-label="Saving">
                <span className="spinner" />
              </span>
            )}
          </div>
          <p className="status" aria-live="polite">
            {phase === 'idle' && (
              <>
                Tap to record
                <small>
                  or{' '}
                  <button className="link" onClick={() => setPhase('typing')}>
                    type it instead
                  </button>
                </small>
              </>
            )}
            {phase === 'recording' && (
              <>
                {clock(seconds)}
                <small>Tap again when you are done</small>
              </>
            )}
            {phase === 'working' && (
              <>
                Transcribing and painting
                <small>A minute of speech takes about five seconds</small>
              </>
            )}
          </p>
        </>
      )}

      {error ? <ErrorNote message={error} /> : null}

      <p className="promise">
        <LockIcon size={15} />
        {privacy?.local_only === false ? 'Stored encrypted.' : 'Nothing leaves this machine.'} {audioPromise}
      </p>

      {latest ? (
        <section style={{ width: '100%', textAlign: 'left' }}>
          <h2 className="section">Most recent</h2>
          <div className="group">
            <EntryRow entry={latest} />
          </div>
        </section>
      ) : entries ? (
        <section style={{ width: '100%' }}>
          <h2 className="section" style={{ textAlign: 'left' }}>
            How it works
          </h2>
          <div className="steps">
            {STEPS.map((step) => (
              <div key={step.art} className="card step">
                <img src={`/art/${step.art}.png`} alt="" />
                <div>
                  <b>{step.title}</b>
                  <span>{step.text}</span>
                </div>
              </div>
            ))}
          </div>
        </section>
      ) : null}
    </main>
  )
}
