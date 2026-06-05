import fs from 'node:fs/promises'
import path from 'node:path'
import zlib from 'node:zlib'

const port = Number(process.env.SHELL_WEB_UI_DEBUG_PORT || process.argv[2] || 9235)
const outDir = path.resolve(process.argv[3] || '.shell_runtime/orb_voice_reactivity_cdp_probe')
const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

async function fetchJson(url, timeoutMs = 5000) {
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), timeoutMs)
  try {
    const response = await fetch(url, { signal: controller.signal })
    if (!response.ok) throw new Error(`${response.status} ${response.statusText}`)
    return await response.json()
  } finally {
    clearTimeout(timeout)
  }
}

async function getTarget() {
  let targets
  const errors = []
  for (const endpoint of ['json', 'json/list']) {
    try {
      targets = await fetchJson(`http://127.0.0.1:${port}/${endpoint}`)
      break
    } catch (error) {
      errors.push(`${endpoint}: ${error?.message || error}`)
    }
  }
  if (!Array.isArray(targets)) {
    throw new Error(`Could not read Chrome targets on port ${port}: ${errors.join('; ')}`)
  }
  const target = targets.find((item) => item.type === 'page' && item.webSocketDebuggerUrl)
  if (!target) throw new Error(`No debuggable page found on port ${port}`)
  return target
}

function connect(url) {
  return new Promise((resolve, reject) => {
    const ws = new WebSocket(url)
    let id = 0
    const pending = new Map()
    const events = []
    ws.onopen = () => {
      resolve({
        events,
        send(method, params = {}) {
          return new Promise((innerResolve, innerReject) => {
            const callId = ++id
            pending.set(callId, { innerResolve, innerReject })
            ws.send(JSON.stringify({ id: callId, method, params }))
          })
        },
        close() {
          ws.close()
        },
      })
    }
    ws.onerror = (event) => reject(event)
    ws.onmessage = (event) => {
      const message = JSON.parse(event.data)
      if (message.id && pending.has(message.id)) {
        const entry = pending.get(message.id)
        pending.delete(message.id)
        if (message.error) entry.innerReject(new Error(JSON.stringify(message.error)))
        else entry.innerResolve(message)
        return
      }
      events.push(message)
    }
  })
}

async function evaluate(client, expression) {
  const response = await client.send('Runtime.evaluate', {
    expression,
    awaitPromise: true,
    returnByValue: true,
  })
  if (response.result?.exceptionDetails) {
    throw new Error(response.result.exceptionDetails.text || 'Runtime evaluation failed')
  }
  return response.result.result.value
}

async function waitForReady(client) {
  const deadline = Date.now() + 20000
  while (Date.now() < deadline) {
    const ready = await evaluate(
      client,
      `(() => {
        const canvas = Array.from(document.querySelectorAll('canvas')).find((candidate) => {
          const rect = candidate.getBoundingClientRect()
          return rect.width > 120 && rect.height > 120
        })
        return Boolean(window.shellAPI && canvas)
      })()`,
    )
    if (ready) return true
    await wait(250)
  }
  return false
}

async function readinessSnapshot(client) {
  return evaluate(
    client,
    `(() => {
      const scripts = Array.from(document.scripts).map((script) => script.src || '[inline]')
      const canvases = Array.from(document.querySelectorAll('canvas')).map((canvas) => {
        const rect = canvas.getBoundingClientRect()
        return { width: canvas.width, height: canvas.height, rectWidth: rect.width, rectHeight: rect.height }
      })
      return {
        url: location.href,
        title: document.title,
        readyState: document.readyState,
        shellAPI: Boolean(window.shellAPI),
        probeEmit: Boolean(window.__shellProbeEmit),
        canvasCount: canvases.length,
        canvases,
        bodyText: document.body ? document.body.innerText.slice(0, 1000) : '',
        scripts,
      }
    })()`,
  )
}

async function canvasRect(client) {
  return evaluate(
    client,
    `(() => {
      const canvas = Array.from(document.querySelectorAll('canvas'))
        .map((candidate) => ({ candidate, rect: candidate.getBoundingClientRect() }))
        .sort((a, b) => (b.rect.width * b.rect.height) - (a.rect.width * a.rect.height))[0]?.candidate
      const rect = canvas.getBoundingClientRect()
      return { x: rect.x, y: rect.y, width: rect.width, height: rect.height, scale: window.devicePixelRatio || 1 }
    })()`,
  )
}

async function screenshotCanvas(client, rect, name) {
  const response = await client.send('Page.captureScreenshot', {
    format: 'png',
    fromSurface: true,
    clip: {
      x: Math.max(0, rect.x),
      y: Math.max(0, rect.y),
      width: Math.max(1, rect.width),
      height: Math.max(1, rect.height),
      scale: 1,
    },
  })
  const file = path.join(outDir, `${name}.png`)
  await fs.writeFile(file, Buffer.from(response.result.data, 'base64'))
  return file
}

function unfilterPngRow(filterType, row, previousRow, bytesPerPixel) {
  const out = Buffer.alloc(row.length)
  for (let i = 0; i < row.length; i++) {
    const left = i >= bytesPerPixel ? out[i - bytesPerPixel] : 0
    const up = previousRow ? previousRow[i] : 0
    const upperLeft = previousRow && i >= bytesPerPixel ? previousRow[i - bytesPerPixel] : 0
    let value = row[i]
    if (filterType === 1) value = (value + left) & 0xff
    else if (filterType === 2) value = (value + up) & 0xff
    else if (filterType === 3) value = (value + Math.floor((left + up) / 2)) & 0xff
    else if (filterType === 4) {
      const p = left + up - upperLeft
      const pa = Math.abs(p - left)
      const pb = Math.abs(p - up)
      const pc = Math.abs(p - upperLeft)
      const predictor = pa <= pb && pa <= pc ? left : pb <= pc ? up : upperLeft
      value = (value + predictor) & 0xff
    } else if (filterType !== 0) {
      throw new Error(`Unsupported PNG filter type ${filterType}`)
    }
    out[i] = value
  }
  return out
}

function decodePng(buffer) {
  const signature = buffer.subarray(0, 8).toString('hex')
  if (signature !== '89504e470d0a1a0a') throw new Error('Invalid PNG signature')
  let offset = 8
  let width = 0
  let height = 0
  let bitDepth = 0
  let colorType = 0
  let interlace = 0
  const idatChunks = []
  while (offset < buffer.length) {
    const length = buffer.readUInt32BE(offset)
    const type = buffer.subarray(offset + 4, offset + 8).toString('ascii')
    const data = buffer.subarray(offset + 8, offset + 8 + length)
    if (type === 'IHDR') {
      width = data.readUInt32BE(0)
      height = data.readUInt32BE(4)
      bitDepth = data[8]
      colorType = data[9]
      interlace = data[12]
    } else if (type === 'IDAT') {
      idatChunks.push(data)
    } else if (type === 'IEND') {
      break
    }
    offset += 12 + length
  }
  if (bitDepth !== 8 || interlace !== 0) {
    throw new Error(`Unsupported PNG format: bitDepth=${bitDepth}, interlace=${interlace}`)
  }
  const channels = colorType === 6 ? 4 : colorType === 2 ? 3 : colorType === 0 ? 1 : 0
  if (!channels) throw new Error(`Unsupported PNG color type ${colorType}`)
  const bytesPerPixel = channels
  const rowLength = width * channels
  const inflated = zlib.inflateSync(Buffer.concat(idatChunks))
  const pixels = Buffer.alloc(width * height * 4)
  let sourceOffset = 0
  let previousRow = null
  for (let y = 0; y < height; y++) {
    const filterType = inflated[sourceOffset++]
    const rawRow = inflated.subarray(sourceOffset, sourceOffset + rowLength)
    sourceOffset += rowLength
    const row = unfilterPngRow(filterType, rawRow, previousRow, bytesPerPixel)
    for (let x = 0; x < width; x++) {
      const source = x * channels
      const target = (y * width + x) * 4
      if (channels === 1) {
        pixels[target] = row[source]
        pixels[target + 1] = row[source]
        pixels[target + 2] = row[source]
        pixels[target + 3] = 255
      } else {
        pixels[target] = row[source]
        pixels[target + 1] = row[source + 1]
        pixels[target + 2] = row[source + 2]
        pixels[target + 3] = channels === 4 ? row[source + 3] : 255
      }
    }
    previousRow = row
  }
  return { width, height, pixels }
}

async function pngStats(file) {
  const { width, height, pixels } = decodePng(await fs.readFile(file))
  const cx = width / 2
  const cy = height / 2
  const maxRadius = Math.max(1, Math.hypot(cx, cy))
  const radii = []
  let bright = 0
  let outer = 0
  let white = 0
  let lumaSum = 0
  let greenSum = 0
  let samples = 0
  const step = 2
  for (let y = 0; y < height; y += step) {
    for (let x = 0; x < width; x += step) {
      const i = (y * width + x) * 4
      const r = pixels[i]
      const g = pixels[i + 1]
      const b = pixels[i + 2]
      const luma = r * 0.299 + g * 0.587 + b * 0.114
      samples++
      lumaSum += luma
      greenSum += g
      if (luma > 20) {
        bright++
        const radius = Math.hypot(x - cx, y - cy) / maxRadius
        radii.push(radius)
        if (radius > 0.42) outer++
        if (r > 180 && g > 180 && b > 180) white++
      }
    }
  }
  radii.sort((a, b) => a - b)
  const at = (p) => radii.length ? radii[Math.min(radii.length - 1, Math.floor(radii.length * p))] : 0
  return {
    ok: true,
    width,
    height,
    samples,
    brightPixels: bright,
    outerBrightPixels: outer,
    whitePixels: white,
    avgLuma: Number((lumaSum / Math.max(1, samples)).toFixed(4)),
    avgGreen: Number((greenSum / Math.max(1, samples)).toFixed(4)),
    brightRadiusP90: Number(at(0.9).toFixed(5)),
    brightRadiusP98: Number(at(0.98).toFixed(5)),
  }
}

async function canvasStats(client) {
  return evaluate(
    client,
    `(() => {
      const canvas = Array.from(document.querySelectorAll('canvas'))
        .map((candidate) => ({ candidate, rect: candidate.getBoundingClientRect() }))
        .sort((a, b) => (b.rect.width * b.rect.height) - (a.rect.width * a.rect.height))[0]?.candidate
      const gl = canvas && (canvas.getContext('webgl2') || canvas.getContext('webgl'))
      if (!canvas || !gl) return { ok: false, reason: 'missing canvas/webgl' }
      const width = Math.min(canvas.width, 900)
      const height = Math.min(canvas.height, 900)
      const pixels = new Uint8Array(width * height * 4)
      gl.readPixels(0, 0, width, height, gl.RGBA, gl.UNSIGNED_BYTE, pixels)
      const cx = width / 2
      const cy = height / 2
      const maxRadius = Math.max(1, Math.hypot(cx, cy))
      const radii = []
      let bright = 0
      let outer = 0
      let white = 0
      let lumaSum = 0
      let greenSum = 0
      let samples = 0
      const step = 2
      for (let y = 0; y < height; y += step) {
        for (let x = 0; x < width; x += step) {
          const i = (y * width + x) * 4
          const r = pixels[i]
          const g = pixels[i + 1]
          const b = pixels[i + 2]
          const luma = r * 0.299 + g * 0.587 + b * 0.114
          samples++
          lumaSum += luma
          greenSum += g
          if (luma > 20) {
            bright++
            const radius = Math.hypot(x - cx, y - cy) / maxRadius
            radii.push(radius)
            if (radius > 0.42) outer++
            if (r > 180 && g > 180 && b > 180) white++
          }
        }
      }
      radii.sort((a, b) => a - b)
      const at = (p) => radii.length ? radii[Math.min(radii.length - 1, Math.floor(radii.length * p))] : 0
      return {
        ok: true,
        width,
        height,
        samples,
        brightPixels: bright,
        outerBrightPixels: outer,
        whitePixels: white,
        avgLuma: Number((lumaSum / Math.max(1, samples)).toFixed(4)),
        avgGreen: Number((greenSum / Math.max(1, samples)).toFixed(4)),
        brightRadiusP90: Number(at(0.9).toFixed(5)),
        brightRadiusP98: Number(at(0.98).toFixed(5)),
      }
    })()`,
  )
}

async function injectVoiceAmplitude(client) {
  for (let i = 0; i < 18; i++) {
    await evaluate(
      client,
      `(() => {
        if (window.__shellProbeEmit) {
          window.__shellProbeEmit('voice-status', { state: 'listening', actualRuntime: false, probe: true })
          window.__shellProbeEmit('speech-status', { state: 'speaking', engine: 'probe' })
          window.__shellProbeEmit('voice-amplitude', { value: 0.95, probe: true })
          return { success: true, source: 'browser-probe' }
        }
        return window.shellAPI.call('probe-voice-amplitude', { value: 0.95, speaking: true })
      })()`,
    )
    await wait(90)
  }
}

await fs.mkdir(outDir, { recursive: true })
const report = { ok: false, probeVersion: 'screenshot-pixels-v4', port, screenshots: {}, metrics: {}, errors: [] }
let client
try {
  const target = await getTarget()
  client = await connect(target.webSocketDebuggerUrl)
  await client.send('Page.enable')
  await client.send('Runtime.enable')
  if (!(await waitForReady(client))) {
    report.debug = await readinessSnapshot(client)
    report.consoleEvents = client.events
      .filter((event) => event.method && /Runtime|Log|Inspector|Page/.test(event.method))
      .slice(-40)
    throw new Error('Dashboard canvas did not become ready')
  }
  const rect = await canvasRect(client)
  report.canvasRect = rect
  await wait(1000)
  report.screenshots.idle = await screenshotCanvas(client, rect, 'orb_idle')
  const idleWebglStats = await canvasStats(client)
  const idleStats = await pngStats(report.screenshots.idle)
  await injectVoiceAmplitude(client)
  await wait(200)
  report.screenshots.voiceReactive = await screenshotCanvas(client, rect, 'orb_voice_reactive')
  const reactiveWebglStats = await canvasStats(client)
  const reactiveStats = await pngStats(report.screenshots.voiceReactive)
  const radiusP98Delta = Number((reactiveStats.brightRadiusP98 - idleStats.brightRadiusP98).toFixed(5))
  const whitePixelDelta = reactiveStats.whitePixels - idleStats.whitePixels
  const outerBrightDelta = reactiveStats.outerBrightPixels - idleStats.outerBrightPixels
  const lumaDelta = Number((reactiveStats.avgLuma - idleStats.avgLuma).toFixed(4))
  report.metrics = {
    idle: idleStats,
    voiceReactive: reactiveStats,
    webglReadPixels: {
      idle: idleWebglStats,
      voiceReactive: reactiveWebglStats,
    },
    radiusP98Delta,
    whitePixelDelta,
    outerBrightDelta,
    lumaDelta,
  }
  const canvasNonblank = idleStats.ok && reactiveStats.ok && idleStats.brightPixels > 100 && reactiveStats.brightPixels > 100
  const visibleReaction =
    radiusP98Delta > 0.008 ||
    whitePixelDelta > 40 ||
    outerBrightDelta > 40 ||
    Math.abs(lumaDelta) > 0.015
  report.ok = Boolean(canvasNonblank && visibleReaction)
  if (!canvasNonblank) report.errors.push('Canvas appeared blank in one or more sampled frames.')
  if (!visibleReaction) report.errors.push('Voice amplitude did not cause measurable orb canvas change.')
} catch (error) {
  report.errors.push(String(error?.message || error))
} finally {
  if (client) client.close()
}
const reportPath = path.join(outDir, 'report.json')
await fs.writeFile(reportPath, JSON.stringify(report, null, 2))
console.log(JSON.stringify({ ...report, reportPath }, null, 2))
process.exit(report.ok ? 0 : 2)
