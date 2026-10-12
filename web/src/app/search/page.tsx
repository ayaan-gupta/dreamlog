'use client'

import { useRouter, useSearchParams } from 'next/navigation'
import type { FormEvent } from 'react'
import { Suspense, useEffect, useState } from 'react'
import { Empty, EntryRow, ErrorNote } from '@/components/bits'
import { SearchIcon } from '@/components/icons'
import { api } from '@/lib/api'
import { plural } from '@/lib/format'
import type { SearchResult } from '@/lib/types'

const IDEAS = ['dreams about water', 'being chased', 'my mother', 'a house with hidden rooms', 'being late']

function Search() {
  const router = useRouter()
  const params = useSearchParams()
  const query = params.get('q') ?? ''
  const [draft, setDraft] = useState(query)
  const [result, setResult] = useState<SearchResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    setDraft(query)
    if (!query.trim()) {
      setResult(null)
      return
    }
    let live = true
    setBusy(true)
    setError(null)
    api
      .search(query)
      .then((value) => live && setResult(value))
      .catch((reason: unknown) => live && setError(reason instanceof Error ? reason.message : 'Search failed.'))
      .finally(() => live && setBusy(false))
    return () => {
      live = false
    }
  }, [query])

  const go = (text: string) => router.push(text.trim() ? `/search?q=${encodeURIComponent(text.trim())}` : '/search')
  const submit = (event: FormEvent) => {
    event.preventDefault()
    go(draft)
  }

  return (
    <main>
      <h1 className="title">Search</h1>
      <p className="lede">By meaning, not by exact words.</p>
      <form className="searchbar" onSubmit={submit} role="search">
        <SearchIcon size={20} />
        <input
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="dreams about water"
          aria-label="Search your dreams"
          enterKeyHint="search"
          autoCapitalize="none"
        />
      </form>
      <div className="meta" style={{ marginTop: 14 }}>
        {IDEAS.map((idea) => (
          <button key={idea} className="chip" aria-pressed={idea === query} onClick={() => go(idea)}>
            {idea}
          </button>
        ))}
      </div>

      {error ? <ErrorNote message={error} /> : null}

      {result && !busy ? (
        result.hits.length ? (
          <>
            <h2 className="section">{plural(result.hits.length, 'dream')}</h2>
            <p className="small" style={{ margin: '0 4px 10px' }}>
              {result.matched_symbol
                ? `Dreams with the symbol ${result.matched_symbol} come first, then dreams close in meaning to "${result.cleaned}".`
                : `Ranked by how close each dream is in meaning to "${result.cleaned}". The number is cosine similarity.`}
            </p>
            <div className="group">
              {result.hits.map((hit) => (
                <EntryRow
                  key={hit.entry.id}
                  entry={hit.entry}
                  symbols={2}
                  trailing={
                    <span className="score" title={hit.via === 'meaning' ? 'close in meaning' : `has the symbol ${result.matched_symbol ?? ''}`}>
                      {hit.via === 'meaning' ? hit.score.toFixed(2) : 'symbol'}
                    </span>
                  }
                />
              ))}
            </div>
          </>
        ) : (
          <div style={{ marginTop: 24 }}>
            <Empty art="empty-search" title="Nothing close to that">
              No dream is near &quot;{result.cleaned}&quot; in meaning, and no symbol matches it.
            </Empty>
          </div>
        )
      ) : null}
    </main>
  )
}

export default function SearchPage() {
  return (
    <Suspense fallback={<main />}>
      <Search />
    </Suspense>
  )
}
