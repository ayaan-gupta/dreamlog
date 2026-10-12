/** Shapes returned by the API. Mirrors api/dreamlog/models.py. */

export interface DreamSymbol {
  id: number
  name: string
  kind: string
  salience: number
  surfaces: string[]
  glyph: string | null
}

export interface Entry {
  id: string
  created_at: string
  updated_at: string
  transcript: string
  title: string
  moods: string[]
  symbols: DreamSymbol[]
  image_url: string | null
  thumb_url: string | null
  has_audio: boolean
  duration_s: number | null
  source: string
  engines: Record<string, string>
  timings_ms: Record<string, number> | null
}

export interface GraphNode {
  id: number
  name: string
  kind: string
  glyph: string | null
  count: number
  aliases: string[]
  cluster: number | null
}

export interface GraphEdge {
  source: number
  target: number
  weight: number
}

export interface GraphCluster {
  id: number
  name: string
  named_by: string
  members: number[]
}

export interface Graph {
  nodes: GraphNode[]
  edges: GraphEdge[]
  clusters: GraphCluster[]
  entries: number
}

export interface SearchHit {
  entry: Entry
  score: number
  via: 'symbol' | 'meaning' | 'both'
}

export interface SearchResult {
  query: string
  cleaned: string
  matched_symbol: string | null
  matched_similarity: number | null
  hits: SearchHit[]
}

export interface Month {
  month: string
  entries: number
}

export interface Atlas {
  month: string
  mood: string
  symbols: { name: string; glyph: string | null; strength: number; entries: number }[]
  image_url: string
}

export interface Privacy {
  local_only: boolean
  transcriber: string
  extractor: string
  embedder: string
  illustrator: string
  keep_audio: boolean
  key_source: 'environment' | 'generated'
  entries: number
  symbols: number
  files: number
  audio_files: number
  encrypted: string[]
  not_encrypted: string[]
}

export interface SeedStatus {
  running: boolean
  done: number
  total: number
  error: string | null
}

export interface Meta {
  disclaimer: string
  moods: Record<string, string>
}
