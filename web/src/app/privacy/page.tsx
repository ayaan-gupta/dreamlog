'use client'

import { useEffect, useState } from 'react'
import { Disclaimer, ErrorNote, useLoad } from '@/components/bits'
import { DownloadIcon, LockIcon } from '@/components/icons'
import { api } from '@/lib/api'
import { engineLabel, plural } from '@/lib/format'
import type { SeedStatus } from '@/lib/types'

export default function PrivacyPage() {
  const { data: status, error, reload } = useLoad(() => api.privacy())
  const [confirming, setConfirming] = useState(false)
  const [busy, setBusy] = useState(false)
  const [note, setNote] = useState<string | null>(null)
  const [seed, setSeed] = useState<SeedStatus | null>(null)

  useEffect(() => {
    if (!seed?.running) return
    const timer = setInterval(() => {
      api
        .sampleStatus()
        .then((next) => {
          setSeed(next)
          if (!next.running) {
            setNote(next.error ? 'The sample dreams could not be loaded.' : 'Sample dreams loaded. They are on the timeline.')
            reload()
          }
        })
        .catch(() => undefined)
    }, 500)
    return () => clearInterval(timer)
  }, [seed?.running, reload])

  const deleteAll = async () => {
    setBusy(true)
    try {
      const gone = await api.deleteAll()
      setNote(`Deleted ${plural(gone.entries, 'dream')} and ${plural(gone.files, 'file')}. Nothing is left.`)
      reload()
    } catch (reason) {
      setNote(reason instanceof Error ? reason.message : 'Delete failed.')
    } finally {
      setBusy(false)
      setConfirming(false)
    }
  }

  const loadSamples = async () => {
    setNote(null)
    try {
      setSeed(await api.loadSamples())
    } catch (reason) {
      setNote(reason instanceof Error ? reason.message : 'The sample dreams could not be loaded.')
    }
  }

  const parts = status
    ? [
        { label: 'Transcription', engine: engineLabel(status.transcriber) },
        { label: 'Symbols and moods', engine: engineLabel(status.extractor) },
        { label: 'Embeddings', engine: engineLabel(status.embedder) },
        { label: 'Pictures', engine: engineLabel(status.illustrator) },
      ]
    : []

  return (
    <main>
      <h1 className="title">Privacy and data</h1>
      {error ? <ErrorNote message={error} /> : null}

      {status ? (
        <>
          <p className="notice" style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
            <LockIcon size={20} />
            <span>
              {status.local_only
                ? 'Nothing leaves this machine. Speech, symbols and pictures are all worked out here.'
                : 'Part of the pipeline uses an outside service. The rows below say which.'}
            </span>
          </p>

          <h2 className="section">Where the work happens</h2>
          <div className="group">
            {parts.map((part) => (
              <div key={part.label} className="row">
                <span className="grow">{part.label}</span>
                <span className="value">
                  {part.engine.name}
                  {part.engine.local ? '' : ', sent out'}
                </span>
              </div>
            ))}
          </div>

          <h2 className="section">What is kept</h2>
          <div className="group">
            <div className="row">
              <span className="grow">Audio</span>
              <span className="value">{status.keep_audio ? `Kept, encrypted (${status.audio_files})` : 'Deleted after transcription'}</span>
            </div>
            <div className="row">
              <span className="grow">Encrypted at rest</span>
              <span className="value">{status.encrypted.join(', ')}</span>
            </div>
            <div className="row">
              <span className="grow">Not encrypted</span>
              <span className="value">{status.not_encrypted.join(', ')}</span>
            </div>
            <div className="row">
              <span className="grow">Encryption key</span>
              <span className="value">{status.key_source === 'environment' ? 'Set by you' : 'Made on this machine, stored beside the data'}</span>
            </div>
            <div className="row">
              <span className="grow">Stored now</span>
              <span className="value">
                {plural(status.entries, 'dream')}, {plural(status.symbols, 'symbol')}, {plural(status.files, 'file')}
              </span>
            </div>
          </div>
          <p className="small" style={{ margin: '10px 4px 0' }}>
            Search and the graph are computed on the unencrypted parts inside the database. Someone holding the database without the key could
            see which symbols recur and roughly what a dream was about, but not its words.
            {status.key_source === 'generated' ? ' With a key stored beside the data, encryption protects a copied database, not a copied disk. Set DREAMLOG_ENCRYPTION_KEY for more.' : ''}
          </p>

          <h2 className="section">Your data</h2>
          <div className="group">
            <a className="row" href="/api/export" download="dreamlog-export.zip">
              <span className="grow">Export everything</span>
              <span className="value" style={{ display: 'inline-flex', gap: 6, alignItems: 'center' }}>
                .zip <DownloadIcon size={17} />
              </span>
            </a>
            <button className="row" onClick={loadSamples} disabled={seed?.running}>
              <span className="grow">Load 30 sample dreams</span>
              <span className="value">{seed?.running ? `${seed.done} of ${seed.total}` : 'Fictional, for trying it out'}</span>
            </button>
            <button className="row danger" onClick={() => setConfirming(true)}>
              Delete everything
            </button>
          </div>
          {seed?.running ? (
            <div className="progress" style={{ margin: '12px 4px 0' }}>
              <i style={{ width: `${Math.round((seed.done / Math.max(seed.total, 1)) * 100)}%` }} />
            </div>
          ) : null}
          {note ? (
            <p className="notice" role="status">
              {note}
            </p>
          ) : null}

          <h2 className="section">What this is not</h2>
          <Disclaimer />
        </>
      ) : null}

      {confirming ? (
        <div className="scrim" role="dialog" aria-modal="true" aria-labelledby="wipe-title">
          <div className="dialog">
            <h2 id="wipe-title">Delete everything?</h2>
            <p>Every dream, picture, recording, symbol and embedding is removed from the database and the disk. This cannot be undone. Export first if you want a copy.</p>
            <div className="actions">
              <button className="button danger" onClick={deleteAll} disabled={busy}>
                Delete everything
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
