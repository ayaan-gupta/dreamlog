import { describe, expect, it } from 'vitest'
import type { LayoutEdge, LayoutNode } from '@/lib/layout'
import { layout, nodeRadius } from '@/lib/layout'

function sample(count: number): { nodes: LayoutNode[]; edges: LayoutEdge[] } {
  const nodes = Array.from({ length: count }, (_, i) => ({ id: i + 1, radius: nodeRadius(1 + (i % 5)) }))
  const edges: LayoutEdge[] = []
  for (let i = 1; i <= count; i++) {
    if (i + 1 <= count) edges.push({ source: i, target: i + 1, weight: 1 + (i % 3) })
    if (i * 2 <= count) edges.push({ source: i, target: i * 2, weight: 1 })
  }
  return { nodes, edges }
}

describe('graph layout', () => {
  it('is deterministic: the same graph always gets the same picture', () => {
    const { nodes, edges } = sample(30)
    const first = layout(nodes, edges, { width: 900, height: 560 })
    const second = layout([...nodes].reverse(), [...edges].reverse(), { width: 900, height: 560 })
    for (const node of nodes) expect(second.get(node.id)).toEqual(first.get(node.id))
  })

  it('keeps every node inside the canvas', () => {
    for (const size of [{ width: 900, height: 560 }, { width: 358, height: 420 }]) {
      const { nodes, edges } = sample(36)
      const placed = layout(nodes, edges, size)
      expect(placed.size).toBe(36)
      for (const node of nodes) {
        const at = placed.get(node.id)!
        expect(at.x).toBeGreaterThanOrEqual(node.radius)
        expect(at.x).toBeLessThanOrEqual(size.width - node.radius)
        expect(at.y).toBeGreaterThanOrEqual(node.radius)
        expect(at.y).toBeLessThanOrEqual(size.height - node.radius)
      }
    }
  })

  it('does not stack nodes on top of each other', () => {
    const { nodes, edges } = sample(24)
    const placed = layout(nodes, edges, { width: 900, height: 560 })
    for (const a of nodes) {
      for (const b of nodes) {
        if (a.id >= b.id) continue
        const pa = placed.get(a.id)!
        const pb = placed.get(b.id)!
        expect(Math.hypot(pa.x - pb.x, pa.y - pb.y)).toBeGreaterThan(a.radius + b.radius)
      }
    }
  })

  it('pulls linked nodes closer than unlinked ones', () => {
    const nodes = [1, 2, 3, 4, 5, 6].map((id) => ({ id, radius: 10 }))
    const placed = layout(nodes, [{ source: 1, target: 2, weight: 4 }], { width: 800, height: 600 })
    const distance = (a: number, b: number) => Math.hypot(placed.get(a)!.x - placed.get(b)!.x, placed.get(a)!.y - placed.get(b)!.y)
    const others = [3, 4, 5, 6].map((id) => distance(1, id))
    expect(distance(1, 2)).toBeLessThan(Math.min(...others))
  })

  it('handles the empty and single-node cases', () => {
    expect(layout([], [], { width: 400, height: 300 }).size).toBe(0)
    const one = layout([{ id: 7, radius: 12 }], [], { width: 400, height: 300 }).get(7)!
    expect(one.x).toBeGreaterThan(100)
    expect(one.x).toBeLessThan(300)
  })

  it('draws a symbol seen more often as a larger disc', () => {
    expect(nodeRadius(8)).toBeGreaterThan(nodeRadius(2))
    expect(nodeRadius(2, true)).toBeLessThan(nodeRadius(2))
  })
})
