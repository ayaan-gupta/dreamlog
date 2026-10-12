/** Microphone capture with MediaRecorder, plus a level meter for the button. */

const CANDIDATES = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4', 'audio/ogg;codecs=opus'] as const

/** The first container this browser can record. Chrome and Firefox take WebM,
 * Safari takes MP4. The server decodes either. */
export function pickMime(isSupported: (type: string) => boolean): string | null {
  return CANDIDATES.find((type) => isSupported(type)) ?? null
}

export function extensionFor(mime: string): string {
  if (mime.includes('mp4')) return 'm4a'
  if (mime.includes('ogg')) return 'ogg'
  return 'webm'
}

export type MicProblem = 'unsupported' | 'denied' | 'no-device' | 'failed'

export class MicError extends Error {
  constructor(readonly problem: MicProblem) {
    super(problem)
  }
}

export function explain(problem: MicProblem): string {
  switch (problem) {
    case 'unsupported':
      return 'This browser cannot record audio here. Recording needs a secure page (https or localhost).'
    case 'denied':
      return 'The microphone is blocked for this page. Allow it in the address bar, or type the dream instead.'
    case 'no-device':
      return 'No microphone was found.'
    default:
      return 'Recording could not start.'
  }
}

export interface Recording {
  blob: Blob
  mime: string
  seconds: number
}

export class Recorder {
  private stream: MediaStream | null = null
  private recorder: MediaRecorder | null = null
  private context: AudioContext | null = null
  private analyser: AnalyserNode | null = null
  private chunks: Blob[] = []
  private startedAt = 0
  private mime = ''

  async start(): Promise<void> {
    if (typeof MediaRecorder === 'undefined' || !navigator.mediaDevices?.getUserMedia) throw new MicError('unsupported')
    const mime = pickMime((type) => MediaRecorder.isTypeSupported(type))
    if (!mime) throw new MicError('unsupported')
    try {
      this.stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, channelCount: 1 } })
    } catch (error) {
      const name = error instanceof DOMException ? error.name : ''
      if (name === 'NotAllowedError' || name === 'SecurityError') throw new MicError('denied')
      if (name === 'NotFoundError') throw new MicError('no-device')
      throw new MicError('failed')
    }
    this.mime = mime
    this.chunks = []
    this.recorder = new MediaRecorder(this.stream, { mimeType: mime, audioBitsPerSecond: 48_000 })
    this.recorder.addEventListener('dataavailable', (event) => {
      if (event.data.size > 0) this.chunks.push(event.data)
    })
    this.recorder.start(1000)
    this.startedAt = performance.now()
    try {
      this.context = new AudioContext()
      this.analyser = this.context.createAnalyser()
      this.analyser.fftSize = 512
      this.context.createMediaStreamSource(this.stream).connect(this.analyser)
    } catch {
      this.analyser = null // the meter is decoration; recording works without it
    }
  }

  /** Input level from 0 to 1, for the ring around the button. */
  level(): number {
    if (!this.analyser) return 0
    const data = new Uint8Array(this.analyser.fftSize)
    this.analyser.getByteTimeDomainData(data)
    let sum = 0
    for (const value of data) sum += ((value - 128) / 128) ** 2
    return Math.min(1, Math.sqrt(sum / data.length) * 4)
  }

  seconds(): number {
    return this.startedAt ? (performance.now() - this.startedAt) / 1000 : 0
  }

  stop(): Promise<Recording> {
    return new Promise((resolve, reject) => {
      const recorder = this.recorder
      if (!recorder) return reject(new MicError('failed'))
      const seconds = this.seconds()
      recorder.addEventListener(
        'stop',
        () => {
          const blob = new Blob(this.chunks, { type: this.mime.split(';')[0] })
          this.release()
          resolve({ blob, mime: this.mime, seconds })
        },
        { once: true },
      )
      recorder.stop()
    })
  }

  cancel(): void {
    if (this.recorder && this.recorder.state !== 'inactive') this.recorder.stop()
    this.release()
  }

  private release(): void {
    this.stream?.getTracks().forEach((track) => track.stop())
    void this.context?.close()
    this.stream = null
    this.recorder = null
    this.context = null
    this.analyser = null
    this.startedAt = 0
  }
}
