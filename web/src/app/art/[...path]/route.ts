import { readFile } from 'node:fs/promises'
import path from 'node:path'

/**
 * Serves design-time art. A file in assets/generated wins over the code-drawn
 * file at the same relative path in assets/interim, one file at a time, so
 * delivered art takes over without a rebuild.
 */
const ROOT = process.env.DREAMLOG_ASSETS_DIR ?? path.resolve(process.cwd(), '..', 'assets')
const TYPES: Record<string, string> = { '.png': 'image/png', '.webp': 'image/webp', '.svg': 'image/svg+xml', '.jpg': 'image/jpeg' }

export const dynamic = 'force-dynamic'

export async function GET(_request: Request, context: { params: Promise<{ path: string[] }> }): Promise<Response> {
  const { path: segments } = await context.params
  const relative = segments.join('/')
  const type = TYPES[path.extname(relative).toLowerCase()]
  if (!type || segments.some((segment) => segment === '..' || segment.startsWith('.'))) return new Response('not found', { status: 404 })
  for (const source of ['generated', 'interim']) {
    try {
      const data = await readFile(path.join(ROOT, source, relative))
      return new Response(new Uint8Array(data), {
        headers: { 'Content-Type': type, 'Cache-Control': 'public, max-age=300', 'X-Dreamlog-Art': source },
      })
    } catch {
      // try the next source
    }
  }
  return new Response('not found', { status: 404 })
}
