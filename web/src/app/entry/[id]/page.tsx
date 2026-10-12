'use client'

import Link from 'next/link'
import { useParams, useRouter, useSearchParams } from 'next/navigation'
import { Suspense, useEffect, useState } from 'react'
import { ErrorNote, MoodChips, useLoad } from '@/components/bits'
import { api } from '@/lib/api'
import { clock, dayLabel, engineLabel, saidAs } from '@/lib/format'
import type { Entry } from '@/lib/types'

function EntryView() {
  const { id } = useParams<{ id: string }>()
  const router = useRouter()
  const isNew = useSearchParams().get('new') === '1'
  const { data, error } = useLoad(() => api.entry(id), id)
  const [entry, setEntry] = useState<Entry | null>(null)
  const [draft, setDraft] = useState('')
  const [editing, setEditing] = useState(false)
  const [busy, setBusy] = useState(false)
  const [confirming, setConfirming] = useState(false)
  const [problem, setProblem] = useState<string | null>(null)
  const [savedIn, setSavedIn] = useState<number | null>(null)

  useEffect(() => {
    if (!data) return
    setEntry(data)
    setDraft(data.transcript)
    setEditing(isNew)
    const stored = Number(sessionStorage.getItem(`saved-in:${data.id}`))
    setSavedIn(stored > 0 ? stored : null)
  }, [data, isNew])

  if (error) {
    return (
      <main>
        <ErrorNote message={error === 'not found' ? 'That dream is not here any more.' : error} />
      </main>
    )
  }
  if (!entry) return <main />

  const save = async () => {
    setBusy(true)
    setProblem(null)
    try {
      const updated = draft.trim() === entry.transcript ? entry : await api.update(entry.id, draft)
      setEntry(updated)
      setDraft(updated.transcript)
      setEditing(false)
      if (isNew) router.replace(`/entry/${entry.id}`)
    } catch (reason) {
      setProblem(reason instanceof Error ? reason.message : 'That could not be saved.')
    } finally {
      setBusy(false)
    }
  }

  const remove = async () => {
    setBusy(true)
    try {
      await api.remove(entry.id)
      router.push('/timeline')
    } catch (reason) {
      setProblem(reason instanceof Error ? reason.message : 'That could not be deleted.')
      setBusy(false)
      setConfirming(false)
    }
  }

  const transcriber = entry.engines.transcriber ? engineLabel(entry.engines.transcriber) : null
  const total = savedIn

  return (
    <main className="wide">
      <div className="entry">
        {entry.image_url ? (
          <img className="picture" src={entry.image_url} alt="Watercolour painted from this dream's symbols and mood" width={800} height={1000} />
        ) : (
          <span className="picture" />
        )}
        <div>
          <p className="small">
            {dayLabel(entry.created_at)}
            {entry.duration_s ? ` · ${clock(entry.duration_s)} spoken` : ''}
          </p>
          <h1 className="title" style={{ fontSize: 26, marginTop: 4 }}>
            {entry.title}
          </h1>
          <div className="meta" style={{ marginTop: 12 }}>
            <MoodChips moods={entry.moods} />
          </div>

          {isNew && editing ? (
            <p className="notice" style={{ marginTop: 18 }}>
              Saved{total ? `, ${(total / 1000).toFixed(1)} seconds after you stopped` : ''}. Fix anything the transcription got wrong, then keep it.
            </p>
          ) : null}

          <h2 className="section" style={{ marginLeft: 0 }}>
            Transcript
          </h2>
          {editing ? (
            <>
              <textarea className="sheet" value={draft} onChange={(event) => setDraft(event.target.value)} aria-label="Transcript" />
              <div className="actions" style={{ marginTop: 14 }}>
                <button className="button" onClick={save} disabled={busy || draft.trim().length < 3}>
                  {busy ? 'Repainting' : isNew ? 'Keep it' : 'Save changes'}
                </button>
                {!isNew ? (
                  <button
                    className="button quiet"
                    onClick={() => {
                      setDraft(entry.transcript)
                      setEditing(false)
                    }}
                    disabled={busy}
                  >
                    Cancel
                  </button>
                ) : null}
              </div>
            </>
          ) : (
            <>
              <p className="transcript">{entry.transcript}</p>
              <div className="actions" style={{ marginTop: 16 }}>
                <button className="button quiet" onClick={() => setEditing(true)}>
                  Edit
                </button>
              </div>
            </>
          )}
          {problem ? <ErrorNote message={problem} /> : null}

          <h2 className="section" style={{ marginLeft: 0 }}>
            Symbols
          </h2>
          {entry.symbols.length ? (
            <div className="symbols">
              {entry.symbols.map((symbol) => (
                <Link
                  key={symbol.id}
                  href={`/patterns?symbol=${symbol.id}`}
                  className="chip strong"
                  style={{ opacity: 0.55 + 0.45 * symbol.salience, height: 32, fontSize: 14, background: 'var(--surface)' }}
                  title={saidAs(symbol) === symbol.name ? symbol.kind : `${symbol.kind}, counted with ${symbol.name}`}
                >
                  {saidAs(symbol)}
                </Link>
              ))}
            </div>
          ) : (
            <p className="muted">No symbols were found in this one.</p>
          )}

          <p className="small" style={{ marginTop: 26 }}>
            {transcriber ? `Transcribed by ${transcriber.name}${transcriber.local ? ' on this machine' : ''}. ` : ''}
            Symbols by {engineLabel(entry.engines.extractor ?? 'lexicon').name}. Painted by {engineLabel(entry.engines.illustrator ?? 'procedural').name}.
            {entry.has_audio ? ' The recording is kept, encrypted.' : entry.source === 'voice' ? ' The recording was deleted.' : ''}
          </p>

          <div className="group" style={{ marginTop: 22 }}>
            <button className="row danger" onClick={() => setConfirming(true)}>
              Delete this dream
            </button>
          </div>
        </div>
      </div>

      {confirming ? (
        <div className="scrim" role="dialog" aria-modal="true" aria-labelledby="delete-title">
          <div className="dialog">
            <h2 id="delete-title">Delete this dream?</h2>
            <p>The transcript, its picture and any symbols only this dream used are removed. This cannot be undone.</p>
            <div className="actions">
              <button className="button danger" onClick={remove} disabled={busy}>
                Delete
              </button>
              <button className="button quiet" onClick={() => setConfirming(false)} disabled={busy}>
                Cancel
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </main>
  )
}

export default function EntryPage() {
  return (
    <Suspense fallback={<main />}>
      <EntryView />
    </Suspense>
  )
}
