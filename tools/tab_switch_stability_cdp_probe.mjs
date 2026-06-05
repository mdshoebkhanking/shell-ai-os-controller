import fs from 'node:fs/promises'
import path from 'node:path'
import zlib from 'node:zlib'

const port = Number(process.env.SHELL_WEB_UI_DEBUG_PORT || process.argv[2] || 9352)
const outDir = path.resolve(process.argv[3] || '.shell_runtime/tab_switch_stability_ui_probe')
const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

const tabSequence = [
  'Apps',
  'NOTES',
  'GALLERY',
  'CONTROL',
  'SETTINGS',
  'DASHBOARD',
  'Apps',
  'GALLERY',
  'NOTES',
  'DASHBOARD',
]

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

async function waitForShellReady(client) {
  const deadline = Date.now() + 20000
  while (Date.now() < deadline) {
    const ready = await evaluate(
      client,
      `(() => {
        const root = document.querySelector('.shell-ui-root')
        const pane = document.querySelector('.shell-view-pane')
        const layer = document.querySelector('.shell-view-layer')
        if (!root || !pane || !layer) return false
        const rect = layer.getBoundingClientRect()
        return rect.width > 700 && rect.height > 420 && document.readyState !== 'loading'
      })()`,
    )
    if (ready) return true
    await wait(250)
  }
  return false
}

function clickTargetExpression(label) {
  return `
    (() => {
      const target = ${JSON.stringify(label)}.toLowerCase()
      const normalize = (text) => String(text || '').trim().replace(/\\s+/g, ' ')
      const visible = (el) => {
        const rect = el.getBoundingClientRect()
        const style = getComputedStyle(el)
        return rect.width > 1 && rect.height > 1 && style.display !== 'none' && style.visibility !== 'hidden'
      }
      const candidates = Array.from(document.querySelectorAll('button,[role="button"],a,[tabindex]'))
        .filter(visible)
        .map((el) => {
          const text = normalize(el.innerText || el.textContent || '')
          const aria = normalize(el.getAttribute('aria-label') || '')
          const haystacks = [aria, text].filter(Boolean)
          const score = haystacks.some((value) => value.toLowerCase() === target) ? 0 :
            haystacks.some((value) => value.toLowerCase().startsWith(target)) ? 1 :
              haystacks.some((value) => value.toLowerCase().includes(target)) ? 2 : 99
          const rect = el.getBoundingClientRect()
          return {
            score,
            text,
            aria,
            x: rect.left + rect.width / 2,
            y: rect.top + rect.height / 2,
          }
        })
        .filter((item) => item.score < 99)
        .sort((a, b) => a.score - b.score)
      return candidates[0] || null
    })()
  `
}

async function clickTarget(client, label) {
  const rect = await evaluate(client, clickTargetExpression(label))
  if (!rect) return { clicked: false, label, reason: 'not_found' }
  await client.send('Input.dispatchMouseEvent', {
    type: 'mouseMoved',
    x: rect.x,
    y: rect.y,
    button: 'none',
  })
  await client.send('Input.dispatchMouseEvent', {
    type: 'mousePressed',
    x: rect.x,
    y: rect.y,
    button: 'left',
    clickCount: 1,
  })
  await client.send('Input.dispatchMouseEvent', {
    type: 'mouseReleased',
    x: rect.x,
    y: rect.y,
    button: 'left',
    clickCount: 1,
  })
  return {
    clicked: true,
    label,
    text: rect.text,
    aria: rect.aria,
    x: Math.round(rect.x),
    y: Math.round(rect.y),
  }
}

async function clickTab(client, tabId) {
  const result = await clickTarget(client, `Open ${tabId} view`)
  if (result.clicked) return result
  const more = await clickTarget(client, 'Open more Shell views')
  await wait(80)
  const secondResult = await clickTarget(client, `Open ${tabId} view`)
  return { ...secondResult, openedMoreMenu: more.clicked }
}

function unfilterPngRow(filterType, row, previousRow, bytesPerPixel) {
  const out = Buffer.alloc(row.length)
  for (let i = 0; i < row.length; i += 1) {
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
  const inflated = zlib.inflateSync(Buffer.concat(idatChunks))
  const rowLength = width * channels
  const pixels = Buffer.alloc(width * height * 4)
  let sourceOffset = 0
  let previousRow = null
  for (let y = 0; y < height; y += 1) {
    const filterType = inflated[sourceOffset]
    sourceOffset += 1
    const rawRow = inflated.subarray(sourceOffset, sourceOffset + rowLength)
    sourceOffset += rowLength
    const row = unfilterPngRow(filterType, rawRow, previousRow, channels)
    for (let x = 0; x < width; x += 1) {
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
  const stride = Math.max(1, Math.floor(Math.min(width, height) / 160))
  const buckets = new Set()
  let samples = 0
  let bright = 0
  let mid = 0
  let lumaSum = 0
  let maxLuma = 0

  for (let y = 0; y < height; y += stride) {
    for (let x = 0; x < width; x += stride) {
      const idx = (y * width + x) * 4
      const red = pixels[idx]
      const green = pixels[idx + 1]
      const blue = pixels[idx + 2]
      const luma = red * 0.2126 + green * 0.7152 + blue * 0.0722
      samples += 1
      lumaSum += luma
      if (luma > 70) bright += 1
      if (luma > 34) mid += 1
      if (luma > maxLuma) maxLuma = luma
      buckets.add(`${red >> 4}:${green >> 4}:${blue >> 4}`)
    }
  }

  return {
    width,
    height,
    samples,
    meanLuma: Number((lumaSum / Math.max(1, samples)).toFixed(2)),
    maxLuma: Number(maxLuma.toFixed(2)),
    brightRatio: Number((bright / Math.max(1, samples)).toFixed(4)),
    midRatio: Number((mid / Math.max(1, samples)).toFixed(4)),
    colorBuckets: buckets.size,
  }
}

async function captureLayerScreenshot(client, name) {
  const rect = await evaluate(
    client,
    `(() => {
      const layer = document.querySelector('.shell-view-layer')
      if (!layer) return null
      const rect = layer.getBoundingClientRect()
      return {
        x: Math.max(0, rect.x),
        y: Math.max(0, rect.y),
        width: Math.max(1, rect.width),
        height: Math.max(1, rect.height),
      }
    })()`,
  )
  if (!rect) return { file: '', stats: null }
  const response = await client.send('Page.captureScreenshot', {
    format: 'png',
    fromSurface: true,
    clip: { ...rect, scale: 1 },
  })
  const file = path.join(outDir, `${name}.png`)
  await fs.writeFile(file, Buffer.from(response.result.data, 'base64'))
  return { file, stats: await pngStats(file) }
}

async function surfaceSnapshot(client, name) {
  const dom = await evaluate(
    client,
    `(() => {
      const normalize = (text) => String(text || '').trim().replace(/\\s+/g, ' ')
      const layer = document.querySelector('.shell-view-layer')
      const pane = document.querySelector('.shell-view-pane')
      const activeButton = Array.from(document.querySelectorAll('button'))
        .find((button) => button.classList.contains('shell-tab-active') || button.classList.contains('shell-primary-action'))
      const visible = (el) => {
        const rect = el.getBoundingClientRect()
        const style = getComputedStyle(el)
        return rect.width > 2 &&
          rect.height > 2 &&
          style.display !== 'none' &&
          style.visibility !== 'hidden' &&
          Number(style.opacity || 1) > 0.01
      }
      const layerRect = layer?.getBoundingClientRect()
      const paneRect = pane?.getBoundingClientRect()
      const layerText = normalize(layer?.innerText || '')
      const visibleElements = layer
        ? Array.from(layer.querySelectorAll('*')).filter((el) => visible(el))
        : []
      const largeElements = visibleElements.filter((el) => {
        const rect = el.getBoundingClientRect()
        return rect.width > 24 && rect.height > 16
      })
      const skeleton = Boolean(layer?.querySelector('.shell-shimmer')) ||
        /INITIALIZING MODULE/i.test(layerText)
      return {
        title: document.title,
        readyState: document.readyState,
        rootPresent: Boolean(document.querySelector('.shell-ui-root')),
        panePresent: Boolean(pane),
        layerPresent: Boolean(layer),
        paneRect: paneRect ? {
          width: Math.round(paneRect.width),
          height: Math.round(paneRect.height),
        } : null,
        layerRect: layerRect ? {
          width: Math.round(layerRect.width),
          height: Math.round(layerRect.height),
        } : null,
        layerTextLength: layerText.length,
        layerTextPreview: layerText.slice(0, 260),
        visibleElementCount: visibleElements.length,
        largeVisibleElementCount: largeElements.length,
        canvasCount: layer ? layer.querySelectorAll('canvas').length : 0,
        skeleton,
        activeButtonText: normalize(activeButton?.innerText || activeButton?.getAttribute('aria-label') || ''),
      }
    })()`,
  )
  const image = await captureLayerScreenshot(client, name)
  const layerOk =
    dom.rootPresent &&
    dom.panePresent &&
    dom.layerPresent &&
    dom.layerRect?.width >= 700 &&
    dom.layerRect?.height >= 420
  const contentOk =
    dom.layerTextLength >= 18 ||
    dom.largeVisibleElementCount >= 8 ||
    dom.canvasCount > 0
  const imageOk =
    Boolean(image.stats) &&
    image.stats.midRatio > 0.04 &&
    image.stats.colorBuckets > 12 &&
    image.stats.maxLuma > 70

  return {
    name,
    ok: layerOk && contentOk && imageOk,
    layerOk,
    contentOk,
    imageOk,
    dom,
    image,
  }
}

function collectConsoleEvents(events) {
  return events
    .filter((event) =>
      event.method === 'Runtime.consoleAPICalled' ||
      event.method === 'Runtime.exceptionThrown' ||
      event.method === 'Log.entryAdded',
    )
    .map((event) => {
      if (event.method === 'Runtime.consoleAPICalled') {
        return {
          type: event.params.type,
          text: (event.params.args || [])
            .map((arg) => String(arg.value || arg.description || ''))
            .join(' ')
            .slice(0, 500),
        }
      }
      if (event.method === 'Runtime.exceptionThrown') {
        return {
          type: 'exception',
          text: String(event.params.exceptionDetails?.text || event.params.exceptionDetails?.exception?.description || ''),
        }
      }
      return {
        type: event.params.entry?.level || 'log',
        text: String(event.params.entry?.text || '').slice(0, 500),
      }
    })
}

async function main() {
  await fs.mkdir(outDir, { recursive: true })
  const page = await getTarget()
  const client = await connect(page.webSocketDebuggerUrl)
  const report = {
    ok: false,
    targetUrl: page.url,
    snapshots: [],
    clicks: [],
    consoleEvents: [],
  }

  try {
    await client.send('Runtime.enable')
    await client.send('Page.enable')
    await client.send('Log.enable')
    await client.send('Page.bringToFront')

    const ready = await waitForShellReady(client)
    if (!ready) {
      report.ready = false
      report.snapshots.push(await surfaceSnapshot(client, 'not_ready'))
      throw new Error('Shell UI did not become ready')
    }
    report.ready = true
    report.snapshots.push(await surfaceSnapshot(client, 'initial_dashboard'))

    for (let index = 0; index < tabSequence.length; index += 1) {
      const tabId = tabSequence[index]
      const click = await clickTab(client, tabId)
      report.clicks.push({ index, tabId, click })
      if (!click.clicked) {
        report.snapshots.push(await surfaceSnapshot(client, `${String(index).padStart(2, '0')}_${tabId}_click_failed`))
        continue
      }
      await wait(70)
      report.snapshots.push(await surfaceSnapshot(client, `${String(index).padStart(2, '0')}_${tabId}_during`))
      await wait(430)
      report.snapshots.push(await surfaceSnapshot(client, `${String(index).padStart(2, '0')}_${tabId}_settled`))
    }

    report.consoleEvents = collectConsoleEvents(client.events)
    const failedClicks = report.clicks.filter((item) => !item.click.clicked)
    const failedSnapshots = report.snapshots.filter((snapshot) => !snapshot.ok)
    const blockingConsole = report.consoleEvents.filter((event) => event.type === 'exception' || event.type === 'error')
    report.ok = failedClicks.length === 0 && failedSnapshots.length === 0 && blockingConsole.length === 0
    report.summary = {
      clicks: report.clicks.length,
      snapshots: report.snapshots.length,
      failedClicks: failedClicks.length,
      failedSnapshots: failedSnapshots.map((snapshot) => snapshot.name),
      blockingConsole: blockingConsole.length,
    }

    await fs.writeFile(path.join(outDir, 'report.json'), JSON.stringify(report, null, 2))
    if (!report.ok) {
      throw new Error(`Tab switch stability probe failed: ${JSON.stringify(report.summary)}`)
    }
    console.log(JSON.stringify(report.summary, null, 2))
  } finally {
    await fs.writeFile(path.join(outDir, 'report.json'), JSON.stringify(report, null, 2))
    client.close()
  }
}

main().catch((error) => {
  console.error(error?.stack || error?.message || error)
  process.exitCode = 1
})
