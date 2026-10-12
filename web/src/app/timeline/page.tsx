'use client'

import Link from 'next/link'
import { Empty, EntryRow, ErrorNote, useLoad } from '@/components/bits'
import { api } from '@/lib/api'
import { byMonth, monthLabel, plural } from '@/lib/format'

export default function TimelinePage() {
  const { data: entries, error } = useLoad(() => api.entries())
  const groups = entries ? byMonth(entries, Intl.DateTimeFormat().resolvedOptions().timeZone) : []

  return (
    <main>
      <h1 className="title">Timeline</h1>
      {entries ? <p className="lede">{entries.length ? `${plural(entries.length, 'dream')}, newest first.` : 'Nothing here yet.'}</p> : null}
      {error ? <ErrorNote message={error} /> : null}
      {entries && entries.length === 0 ? (
        <div style={{ marginTop: 24 }}>
          <Empty art="empty-timeline" title="No dreams yet">
            Record one from the first tab, or load the 30 sample dreams from{' '}
            <Link href="/privacy" className="link">
              Privacy and data
            </Link>
            .
          </Empty>
        </div>
      ) : null}
      {groups.map((group) => (
        <section key={group.month}>
          <h2 className="section">{monthLabel(group.month)}</h2>
          <div className="group">
            {group.entries.map((entry) => (
              <EntryRow key={entry.id} entry={entry} />
            ))}
          </div>
        </section>
      ))}
    </main>
  )
}
