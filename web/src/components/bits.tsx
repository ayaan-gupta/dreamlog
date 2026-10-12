'use client'

import Link from 'next/link'
import type { ReactNode } from 'react'
import { useEffect, useState } from 'react'
import { api } from '@/lib/api'
import { dayLabel, saidAs } from '@/lib/format'
import type { Entry, Meta } from '@/lib/types'
import { ChevronIcon, InfoIcon } from './icons'

const FALLBACK_META: Meta = {
  disclaimer:
    'Dreamlog reports patterns only. It counts which symbols recur and which appear together. It does not interpret dreams and it is not medical or psychological advice.',
  moods: {},
}

let cachedMeta: Meta | null = null

/** Mood colours and the disclaimer, fetched once per page load. */
export function useMeta(): Meta {
  const [meta, setMeta] = useState<Meta>(cachedMeta ?? FALLBACK_META)
  useEffect(() => {
    if (cachedMeta) return
    api
      .meta()
      .then((value) => {
        cachedMeta = value
        setMeta(value)
      })
      .catch(() => undefined)
  }, [])
  return meta
}

/** Loads something on mount and whenever ``key`` changes. */
export function useLoad<T>(load: () => Promise<T>, key: string | number = 0): { data: T | null; error: string | null; reload: () => void } {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [tick, setTick] = useState(0)
  useEffect(() => {
    let live = true
    setError(null)
    load()
      .then((value) => live && setData(value))
      .catch((reason: unknown) => live && setError(reason instanceof Error ? reason.message : 'Something went wrong.'))
    return () => {
      live = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, tick])
  return { data, error, reload: () => setTick((n) => n + 1) }
}

export function Disclaimer() {
  const meta = useMeta()
  return (
    <aside className="disclaimer" role="note">
      <InfoIcon size={20} />
      <span>{meta.disclaimer}</span>
    </aside>
  )
}

export function MoodChips({ moods }: { moods: string[] }) {
  const meta = useMeta()
  return (
    <>
      {moods.map((mood) => (
        <span key={mood} className="chip strong">
          <i className="dot" style={{ background: meta.moods[mood] ?? 'var(--ink-3)' }} />
          {mood}
        </span>
      ))}
    </>
  )
}

export function EntryRow({ entry, trailing, symbols = 3 }: { entry: Entry; trailing?: ReactNode; symbols?: number }) {
  return (
    <Link href={`/entry/${entry.id}`} className="entry-row">
      {entry.thumb_url ? (
        <img className="thumb" src={entry.thumb_url} alt="" loading="lazy" width={68} height={85} />
      ) : (
        <span className="thumb" />
      )}
      <span style={{ minWidth: 0, flex: 1 }}>
        <span className="small">{dayLabel(entry.created_at)}</span>
        <h3>{entry.title}</h3>
        <span className="meta">
          <MoodChips moods={entry.moods.slice(0, 1)} />
          {entry.symbols.slice(0, symbols).map((symbol) => (
            <span key={symbol.id} className="chip">
              {saidAs(symbol)}
            </span>
          ))}
        </span>
      </span>
      {trailing ?? <ChevronIcon className="chevron" size={18} />}
    </Link>
  )
}

export function Empty({ art, title, children }: { art: string; title: string; children?: ReactNode }) {
  return (
    <div className="card empty">
      <img src={`/art/${art}.png`} alt="" />
      <b>{title}</b>
      {children ? <p>{children}</p> : null}
    </div>
  )
}

export function ErrorNote({ message }: { message: string }) {
  return (
    <p className="notice error" role="alert">
      {message}
    </p>
  )
}
