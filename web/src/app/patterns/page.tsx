'use client'

import { useSearchParams } from 'next/navigation'
import { Suspense, useEffect, useMemo, useRef, useState } from 'react'
import { Disclaimer, Empty, EntryRow, ErrorNote, useLoad, useMeta } from '@/components/bits'
import { api } from '@/lib/api'
import { plural } from '@/lib/format'
import { layout, nodeRadius } from '@/lib/layout'
import type { Graph, GraphNode } from '@/lib/types'

const CLUSTER_ORDER = ['calm', 'nostalgic', 'awed', 'confused', 'tender', 'anxious', 'sad', 'angry', 'fearful', 'joyful']

function GraphView({ graph, selected, onSelect, all }: { graph: Graph; selected: number | null; onSelect: (id: number | null) => void; all: boolean }) {
  const meta = useMeta()
  const frame = useRef<HTMLDivElement | null>(null)
  const [width, setWidth] = useState(0)

  useEffect(() => {
    const element = frame.current
    if (!element) return
    const observer = new ResizeObserver(([entry]) => entry && setWidth(Math.round(entry.contentRect.width)))
    observer.observe(element)
    return () => observer.disconnect()
  }, [])

  const compact = width < 600
  const height = compact ? Math.round(width * 1.18) : Math.round(Math.min(width * 0.6, 620))

  const { nodes, edges, positions } = useMemo(() => {
    const shown = graph.nodes.filter((node) => all || node.count >= 2 || node.id === selected)
    const ids = new Set(shown.map((node) => node.id))
    const links = graph.edges.filter((edge) => ids.has(edge.source) && ids.has(edge.target))
    const placed =
      width > 0
        ? layout(
            shown.map((node) => ({ id: node.id, radius: nodeRadius(node.count, compact) })),
            links,
            { width, height },
          )
        : new Map<number, { x: number; y: number }>()
    return { nodes: shown, edges: links, positions: placed }
  }, [graph, all, selected, width, height, compact])

  const neighbours = useMemo(() => {
    const near = new Set<number>()
    if (selected === null) return near
    for (const edge of edges) {
      if (edge.source === selected) near.add(edge.target)
      if (edge.target === selected) near.add(edge.source)
    }
    return near
  }, [edges, selected])

  const colour = (node: GraphNode): string => {
    if (node.cluster === null) return 'var(--ink-3)'
    const mood = CLUSTER_ORDER[node.cluster % CLUSTER_ORDER.length] ?? 'neutral'
    return meta.moods[mood] ?? 'var(--ink-3)'
  }
  const labelFloor = all ? (compact ? 4 : 3) : compact ? 3 : 2

  return (
    <div className="card graph" ref={frame}>
      {width > 0 ? (
        <svg viewBox={`0 0 ${width} ${height}`} width={width} height={height} role="img" aria-label="Recurring symbols and how often they share a dream" onClick={() => onSelect(null)}>
          <g>
            {edges.map((edge) => {
              const a = positions.get(edge.source)
              const b = positions.get(edge.target)
              if (!a || !b) return null
              const lit = selected !== null && (edge.source === selected || edge.target === selected)
              const dim = selected !== null && !lit
              return (
                <line
                  key={`${edge.source}-${edge.target}`}
                  className={lit ? 'edge lit' : 'edge'}
                  x1={a.x}
                  y1={a.y}
                  x2={b.x}
                  y2={b.y}
                  strokeWidth={lit ? 1.6 + edge.weight * 0.5 : 0.6 + edge.weight * 0.5}
                  strokeOpacity={dim ? 0.05 : lit ? 0.7 : Math.min(0.1 + edge.weight * 0.09, 0.5)}
                />
              )
            })}
          </g>
          {nodes.map((node) => {
            const at = positions.get(node.id)
            if (!at) return null
            const r = nodeRadius(node.count, compact)
            const focus = selected === null || node.id === selected || neighbours.has(node.id)
            const labelled = node.id === selected || (selected !== null ? neighbours.has(node.id) && (node.count >= 2 || neighbours.size < 14) : node.count >= labelFloor)
            return (
              <g key={node.id} opacity={focus ? 1 : 0.22}>
                <circle
                  className={`node${node.id === selected ? ' selected' : ''}`}
                  cx={at.x}
                  cy={at.y}
                  r={r}
                  fill={colour(node)}
                  onClick={(event) => {
                    event.stopPropagation()
                    onSelect(node.id === selected ? null : node.id)
                  }}
                >
                  <title>{`${node.name}: ${plural(node.count, 'dream')}`}</title>
                </circle>
                {labelled ? (
                  <text x={at.x} y={at.y + r + 13} textAnchor="middle">
                    {node.name}
                  </text>
                ) : null}
              </g>
            )
          })}
        </svg>
      ) : (
        <div style={{ height: 420 }} />
      )}
    </div>
  )
}

function Patterns() {
  const params = useSearchParams()
  const { data: graph, error } = useLoad(() => api.graph())
  const [selected, setSelected] = useState<number | null>(null)
  const [all, setAll] = useState(false)
  const { data: dreams } = useLoad(() => (selected === null ? Promise.resolve(null) : api.entries(selected)), selected ?? -1)

  useEffect(() => {
    const wanted = Number(params.get('symbol'))
    if (graph && Number.isInteger(wanted) && graph.nodes.some((node) => node.id === wanted)) setSelected(wanted)
  }, [graph, params])

  const byId = useMemo(() => new Map((graph?.nodes ?? []).map((node) => [node.id, node])), [graph])
  const node = selected === null ? null : (byId.get(selected) ?? null)
  const company = useMemo(() => {
    if (!graph || selected === null) return []
    return graph.edges
      .filter((edge) => edge.source === selected || edge.target === selected)
      .map((edge) => ({ other: byId.get(edge.source === selected ? edge.target : edge.source), weight: edge.weight }))
      .filter((item): item is { other: GraphNode; weight: number } => item.other !== undefined)
      .sort((a, b) => b.weight - a.weight || b.other.count - a.other.count || a.other.name.localeCompare(b.other.name))
      .slice(0, 8)
  }, [graph, selected, byId])

  const recurring = graph?.nodes.filter((item) => item.count >= 2).length ?? 0

  return (
    <main className="wide">
      <h1 className="title">Patterns</h1>
      <p className="lede" style={{ marginBottom: 18 }}>
        {graph
          ? graph.nodes.length
            ? `${plural(graph.nodes.length, 'symbol')} across ${plural(graph.entries, 'dream')}. ${recurring} of them came back at least once.`
            : 'Symbols appear here once there are dreams to count.'
          : ' '}
      </p>
      <Disclaimer />
      {error ? <ErrorNote message={error} /> : null}

      {graph && graph.nodes.length === 0 ? (
        <div style={{ marginTop: 20 }}>
          <Empty art="empty-patterns" title="Nothing to count yet">
            A symbol is drawn larger each time it returns, and joined to the symbols it shares a dream with.
          </Empty>
        </div>
      ) : null}

      {graph && graph.nodes.length > 0 ? (
        <>
          <div className="toolbar">
            <span className="small">Size is how many dreams. A line means two symbols shared a dream. Colour is a cluster of similar symbols.</span>
            <div className="segmented" role="group" aria-label="Which symbols to show">
              <button aria-pressed={!all} onClick={() => setAll(false)}>
                Recurring
              </button>
              <button aria-pressed={all} onClick={() => setAll(true)}>
                All
              </button>
            </div>
          </div>
          <GraphView graph={graph} selected={selected} onSelect={setSelected} all={all} />

          <div className="columns">
            <section>
              <h2 className="section">{node ? node.name : 'Pick a symbol'}</h2>
              {node ? (
                <>
                  <div className="group">
                    <div className="row">
                      <span className="grow">Appears in</span>
                      <span className="value">{plural(node.count, 'dream')}</span>
                    </div>
                    {node.aliases.length > 1 ? (
                      <div className="row">
                        <span className="grow">Counted together</span>
                        <span className="value">{node.aliases.join(', ')}</span>
                      </div>
                    ) : null}
                    {company.length ? (
                      <div className="row" style={{ alignItems: 'flex-start' }}>
                        <span>Appears with</span>
                        <span className="symbols" style={{ flex: 1, justifyContent: 'flex-end' }}>
                          {company.map((item) => (
                            <button key={item.other.id} className="chip strong" onClick={() => setSelected(item.other.id)}>
                              {item.other.name}
                              <span className="muted">{item.weight}</span>
                            </button>
                          ))}
                        </span>
                      </div>
                    ) : null}
                  </div>
                  {dreams?.length ? (
                    <div className="group" style={{ marginTop: 14 }}>
                      {dreams.map((entry) => (
                        <EntryRow key={entry.id} entry={entry} symbols={2} />
                      ))}
                    </div>
                  ) : null}
                </>
              ) : (
                <p className="muted" style={{ padding: '0 4px' }}>
                  Tap a circle to see the dreams it comes from and what it appears with.
                </p>
              )}
            </section>

            <section>
              <h2 className="section">Clusters</h2>
              {graph.clusters.length ? (
                <div className="group">
                  {graph.clusters.map((cluster) => (
                    <div key={cluster.id} className="row" style={{ alignItems: 'flex-start' }}>
                      <span style={{ minWidth: 92, fontWeight: 600 }}>{cluster.name}</span>
                      <span className="symbols" style={{ flex: 1 }}>
                        {cluster.members.map((id) => {
                          const member = byId.get(id)
                          return member ? (
                            <button key={id} className="chip" aria-pressed={id === selected} onClick={() => setSelected(id)}>
                              {member.name}
                            </button>
                          ) : null
                        })}
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="muted" style={{ padding: '0 4px' }}>
                  No clusters yet. They form when several symbols are close to each other.
                </p>
              )}
              {graph.clusters.length ? (
                <p className="small" style={{ margin: '10px 4px 0' }}>
                  Groups come from HDBSCAN on the symbol embeddings.{' '}
                  {graph.clusters[0]?.named_by === 'most-central' ? 'Each is named after its most central member.' : 'Names are written by a language model from the member list.'}
                </p>
              ) : null}
            </section>
          </div>
        </>
      ) : null}
    </main>
  )
}

export default function PatternsPage() {
  return (
    <Suspense fallback={<main className="wide" />}>
      <Patterns />
    </Suspense>
  )
}
