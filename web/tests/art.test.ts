import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import path from 'node:path'
import { beforeAll, describe, expect, it } from 'vitest'

type Handler = (request: Request, context: { params: Promise<{ path: string[] }> }) => Promise<Response>

const root = mkdtempSync(path.join(tmpdir(), 'dreamlog-art-'))
let GET: Handler

const fetchArt = (...segments: string[]) => GET(new Request('http://test/art/x'), { params: Promise.resolve({ path: segments }) })

beforeAll(async () => {
  mkdirSync(path.join(root, 'interim'), { recursive: true })
  mkdirSync(path.join(root, 'generated'), { recursive: true })
  writeFileSync(path.join(root, 'interim', 'logo.png'), 'drawn in code')
  writeFileSync(path.join(root, 'interim', 'empty-search.png'), 'drawn in code too')
  writeFileSync(path.join(root, 'secret.png'), 'outside both folders')
  process.env.DREAMLOG_ASSETS_DIR = root
  GET = ((await import('@/app/art/[...path]/route')) as { GET: Handler }).GET
})

describe('design-time art', () => {
  it('serves the code-drawn file until a delivered one exists', async () => {
    const response = await fetchArt('logo.png')
    expect(response.status).toBe(200)
    expect(response.headers.get('content-type')).toBe('image/png')
    expect(response.headers.get('x-dreamlog-art')).toBe('interim')
    expect(await response.text()).toBe('drawn in code')
  })

  it('prefers a delivered file at the same path, one file at a time', async () => {
    writeFileSync(path.join(root, 'generated', 'logo.png'), 'delivered')
    const logo = await fetchArt('logo.png')
    expect(logo.headers.get('x-dreamlog-art')).toBe('generated')
    expect(await logo.text()).toBe('delivered')
    const other = await fetchArt('empty-search.png')
    expect(other.headers.get('x-dreamlog-art')).toBe('interim')
    rmSync(path.join(root, 'generated', 'logo.png'))
    expect((await fetchArt('logo.png')).headers.get('x-dreamlog-art')).toBe('interim')
  })

  it('answers 404 for missing files, other file types and paths that climb out', async () => {
    expect((await fetchArt('nope.png')).status).toBe(404)
    expect((await fetchArt('logo.txt')).status).toBe(404)
    expect((await fetchArt('..', 'secret.png')).status).toBe(404)
    expect((await fetchArt('.hidden.png')).status).toBe(404)
  })
})
