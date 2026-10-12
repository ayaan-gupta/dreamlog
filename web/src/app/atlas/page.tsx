'use client'

import { useEffect, useState } from 'react'
import { Empty, ErrorNote, MoodChips, useLoad } from '@/components/bits'
import { DownloadIcon } from '@/components/icons'
import { api } from '@/lib/api'
import { monthLabel, plural } from '@/lib/format'

export default function AtlasPage() {
  const { data: months, error } = useLoad(() => api.months())
  const [month, setMonth] = useState<string | null>(null)
  const { data: atlas, error: atlasError } = useLoad(() => (month ? api.atlas(month) : Promise.resolve(null)), month ?? '')
  const [painted, setPainted] = useState(false)

  useEffect(() => {
    if (months?.length && !month) setMonth(months[0]?.month ?? null)
  }, [months, month])
  useEffect(() => setPainted(false), [atlas?.image_url])

  return (
    <main className="wide">
      <h1 className="title">Dream atlas</h1>
      <p className="lede">One poster a month: the six symbols that were strongest, drawn as islands. A dotted line joins two that shared a dream.</p>
      {error ? <ErrorNote message={error} /> : null}

      {months && months.length === 0 ? (
        <div style={{ marginTop: 24 }}>
          <Empty art="empty-atlas" title="No months to chart yet">
            The atlas for a month appears as soon as that month has a dream in it.
          </Empty>
        </div>
      ) : null}

      {months && months.length > 0 ? (
        <div className="months" role="group" aria-label="Month">
          {months.map((item) => (
            <button key={item.month} className="chip" style={{ height: 34, padding: '0 14px', fontSize: 14 }} aria-pressed={item.month === month} onClick={() => setMonth(item.month)}>
              {monthLabel(item.month)}
            </button>
          ))}
        </div>
      ) : null}

      {atlasError ? <ErrorNote message={atlasError} /> : null}

      {atlas && month === atlas.month ? (
        <div className="atlas">
          <div style={{ position: 'relative' }}>
            <img
              className="poster"
              src={atlas.image_url}
              alt={`Dream atlas for ${monthLabel(atlas.month)}: ${atlas.symbols.map((s) => s.name).join(', ')}`}
              width={1000}
              height={1250}
              onLoad={() => setPainted(true)}
              style={{ opacity: painted ? 1 : 0.35, transition: 'opacity 300ms ease' }}
            />
            {!painted ? (
              <p className="small" style={{ position: 'absolute', inset: 0, display: 'grid', placeItems: 'center' }} role="status">
                Painting the poster
              </p>
            ) : null}
          </div>
          <div>
            <h2 className="section" style={{ marginTop: 4 }}>
              {monthLabel(atlas.month)}
            </h2>
            <div className="group">
              {atlas.symbols.map((symbol, index) => (
                <div key={symbol.name} className="row">
                  <span className="rank">{index + 1}</span>
                  <span className="grow" style={{ fontWeight: 600 }}>
                    {symbol.name}
                  </span>
                  <span className="value">{plural(symbol.entries, 'dream')}</span>
                </div>
              ))}
            </div>
            <div className="meta" style={{ margin: '14px 4px' }}>
              <span className="small">Painted in the month&apos;s most common mood</span>
              <MoodChips moods={[atlas.mood]} />
            </div>
            <a className="button" href={`/api/atlas/${atlas.month}/image?format=png&download=true`} download={`dream-atlas-${atlas.month}.png`}>
              <DownloadIcon size={19} />
              Download poster
            </a>
            <p className="small" style={{ marginTop: 12 }}>
              PNG, 1200 by 1500. Strength is the sum of how central a symbol was in each dream that month.
            </p>
          </div>
        </div>
      ) : null}
    </main>
  )
}
