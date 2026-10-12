/**
 * A small deterministic force layout for the recurrence graph.
 *
 * No dependency and no randomness: nodes start on a spiral ordered by id, so
 * the same graph always settles into the same picture. Repulsion between every
 * pair, springs along edges (stronger for symbols that share more dreams), a
 * pull to the centre, then a few passes that push overlapping discs apart.
 */

export interface LayoutNode {
  id: number
  radius: number
}

export interface LayoutEdge {
  source: number
  target: number
  weight: number
}

export interface Point {
  x: number
  y: number
}

export interface LayoutOptions {
  width: number
  height: number
  iterations?: number
  padding?: number
}

export function layout(nodes: LayoutNode[], edges: LayoutEdge[], options: LayoutOptions): Map<number, Point> {
  const { width, height, iterations = 320, padding = 14 } = options
  const cx = width / 2
  const cy = height / 2
  const count = nodes.length
  const positions = new Map<number, Point>()
  if (count === 0) return positions

  const ordered = [...nodes].sort((a, b) => a.id - b.id)
  const xs = new Float64Array(count)
  const ys = new Float64Array(count)
  const index = new Map<number, number>()
  ordered.forEach((node, i) => {
    index.set(node.id, i)
    const angle = i * 2.399963 // the golden angle: an even spiral
    const r = Math.sqrt((i + 0.5) / count) * Math.min(width, height) * 0.42
    xs[i] = cx + Math.cos(angle) * r * (width / Math.min(width, height))
    ys[i] = cy + Math.sin(angle) * r * (height / Math.min(width, height))
  })
  const links = edges
    .map((e) => ({ a: index.get(e.source), b: index.get(e.target), weight: e.weight }))
    .filter((e): e is { a: number; b: number; weight: number } => e.a !== undefined && e.b !== undefined)
    .sort((p, q) => p.a - q.a || p.b - q.b || p.weight - q.weight) // floating point sums depend on order, so fix it

  const k = Math.sqrt((width * height) / count) * 0.56
  const aspect = width / height
  for (let step = 0; step < iterations; step++) {
    const cooling = 1 - step / iterations
    const dx = new Float64Array(count)
    const dy = new Float64Array(count)
    for (let i = 0; i < count; i++) {
      for (let j = i + 1; j < count; j++) {
        let ox = xs[i]! - xs[j]!
        let oy = ys[i]! - ys[j]!
        let d2 = ox * ox + oy * oy
        if (d2 < 0.01) {
          ox = 0.1 * (i - j)
          oy = 0.1
          d2 = ox * ox + oy * oy
        }
        const force = (k * k) / d2
        dx[i]! += ox * force
        dy[i]! += oy * force
        dx[j]! -= ox * force
        dy[j]! -= oy * force
      }
    }
    for (const link of links) {
      const ox = xs[link.a]! - xs[link.b]!
      const oy = ys[link.a]! - ys[link.b]!
      const d = Math.sqrt(ox * ox + oy * oy) || 0.01
      const force = ((d * d) / k) * (0.18 + 0.1 * Math.min(link.weight, 4)) * 0.2
      dx[link.a]! -= (ox / d) * force
      dy[link.a]! -= (oy / d) * force
      dx[link.b]! += (ox / d) * force
      dy[link.b]! += (oy / d) * force
    }
    const limit = Math.max(1, 26 * cooling)
    for (let i = 0; i < count; i++) {
      // Gravity, squashed so a wide canvas gets a wide graph.
      dx[i]! -= ((xs[i]! - cx) / aspect) * 0.11
      dy[i]! -= (ys[i]! - cy) * aspect * 0.11
      const d = Math.sqrt(dx[i]! * dx[i]! + dy[i]! * dy[i]!) || 0.01
      xs[i]! += (dx[i]! / d) * Math.min(d, limit)
      ys[i]! += (dy[i]! / d) * Math.min(d, limit)
    }
  }

  const clamp = () => {
    for (let i = 0; i < count; i++) {
      const r = ordered[i]!.radius + padding
      xs[i] = Math.min(Math.max(xs[i]!, r), width - r)
      ys[i] = Math.min(Math.max(ys[i]!, r), height - r - 12)
    }
  }
  clamp()
  for (let pass = 0; pass < 40; pass++) {
    let moved = false
    for (let i = 0; i < count; i++) {
      for (let j = i + 1; j < count; j++) {
        const ox = xs[i]! - xs[j]!
        const oy = ys[i]! - ys[j]!
        const d = Math.sqrt(ox * ox + oy * oy) || 0.01
        const need = ordered[i]!.radius + ordered[j]!.radius + 10
        if (d < need) {
          const push = (need - d) / 2
          xs[i]! += (ox / d) * push
          ys[i]! += (oy / d) * push
          xs[j]! -= (ox / d) * push
          ys[j]! -= (oy / d) * push
          moved = true
        }
      }
    }
    clamp()
    if (!moved) break
  }
  ordered.forEach((node, i) => positions.set(node.id, { x: xs[i]!, y: ys[i]! }))
  return positions
}

export function nodeRadius(count: number, compact = false): number {
  return (compact ? 5 : 7) + (compact ? 4.2 : 5.6) * Math.sqrt(count)
}
