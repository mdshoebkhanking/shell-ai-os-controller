import fs from 'node:fs/promises'
import path from 'node:path'

const port = Number(process.env.SHELL_WEB_UI_DEBUG_PORT || process.argv[2] || 9235)
const outDir = path.resolve(process.argv[3] || '.shell_runtime/chart_tools_gallery_animation_probe')
const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms))
const PNG_DATA_URL =
  'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII='

async function target() {
  const targets = await fetch(`http://127.0.0.1:${port}/json`).then((response) => response.json())
  const page = targets.find((item) => item.type === 'page' && item.webSocketDebuggerUrl)
  if (!page) throw new Error(`No page target on ${port}`)
  return page
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
        }
      })
    }
    ws.onerror = reject
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
    returnByValue: true
  })
  if (response.result?.exceptionDetails) {
    throw new Error(response.result.exceptionDetails.text || 'Runtime evaluation failed')
  }
  return response.result.result.value
}

async function click(client, label) {
  const rect = await evaluate(client, `
    (() => {
      const target = ${JSON.stringify(label)}.toLowerCase()
      const visible = (el) => {
        const rect = el.getBoundingClientRect()
        const style = getComputedStyle(el)
        return rect.width > 1 && rect.height > 1 && style.display !== 'none' && style.visibility !== 'hidden'
      }
      const normalize = (text) => String(text || '').trim().replace(/\\s+/g, ' ')
      const candidates = Array.from(document.querySelectorAll('button,[role="button"],a,[tabindex]'))
        .filter(visible)
        .map((el) => {
          const text = normalize(el.innerText || el.textContent || '')
          const aria = normalize(el.getAttribute('aria-label') || '')
          const hay = [aria, text].filter(Boolean)
          const score = hay.some((v) => v.toLowerCase() === target) ? 0 :
            hay.some((v) => v.toLowerCase().startsWith(target)) ? 1 :
            hay.some((v) => v.toLowerCase().includes(target)) ? 2 : 99
          const rect = el.getBoundingClientRect()
          return { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2, text, aria, score }
        })
        .filter((item) => item.score < 99)
        .sort((a, b) => a.score - b.score)
      return candidates[0] || null
    })()
  `)
  if (!rect) return { clicked: false, label, reason: 'not_found' }
  await client.send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: rect.x, y: rect.y, button: 'none' })
  await client.send('Input.dispatchMouseEvent', { type: 'mousePressed', x: rect.x, y: rect.y, button: 'left', clickCount: 1 })
  await client.send('Input.dispatchMouseEvent', { type: 'mouseReleased', x: rect.x, y: rect.y, button: 'left', clickCount: 1 })
  return { clicked: true, label, text: rect.text, aria: rect.aria, x: Math.round(rect.x), y: Math.round(rect.y) }
}

async function setPrompt(client, value) {
  const rect = await evaluate(client, `
    (() => {
      const input = document.querySelector('input[placeholder^="Type to Shell"]')
      if (!input) return null
      const rect = input.getBoundingClientRect()
      input.focus()
      const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')?.set
      setter?.call(input, '')
      input.dispatchEvent(new Event('input', { bubbles: true }))
      return { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 }
    })()
  `)
  if (!rect) return { typed: false, reason: 'input_not_found' }
  await client.send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: rect.x, y: rect.y, button: 'none' })
  await client.send('Input.dispatchMouseEvent', { type: 'mousePressed', x: rect.x, y: rect.y, button: 'left', clickCount: 1 })
  await client.send('Input.dispatchMouseEvent', { type: 'mouseReleased', x: rect.x, y: rect.y, button: 'left', clickCount: 1 })
  await client.send('Input.insertText', { text: value })
  await wait(500)
  const current = await evaluate(client, `
    (() => {
      const input = document.querySelector('input[placeholder^="Type to Shell"]')
      return input ? input.value : ''
    })()
  `)
  return { typed: current === value, value: current }
}

async function bodyText(client) {
  return evaluate(client, `document.body.innerText || ''`)
}

async function waitForText(client, pattern, timeout = 12000) {
  const started = Date.now()
  while (Date.now() - started < timeout) {
    const text = await bodyText(client)
    if (pattern.test(text)) return { ok: true, text }
    await wait(300)
  }
  return { ok: false, text: await bodyText(client) }
}

async function waitForChartReady(client, timeout = 8000) {
  const started = Date.now()
  while (Date.now() - started < timeout) {
    const ready = await evaluate(client, `
      (() => {
        const button = Array.from(document.querySelectorAll('button')).find((el) => {
          const aria = String(el.getAttribute('aria-label') || '').toLowerCase()
          return aria === 'send chart prompt'
        })
        return Boolean(button && !button.disabled)
      })()
    `)
    if (ready) return true
    await wait(150)
  }
  return false
}

async function runChartPrompt(client, prompt, expected, name) {
  const readyBefore = await waitForChartReady(client)
  const typed = await setPrompt(client, prompt)
  await waitForChartReady(client)
  const sent = await click(client, 'Send chart prompt')
  const result = await waitForText(client, expected, 25000)
  return {
    name,
    ok: readyBefore && typed.typed && sent.clicked && result.ok,
    readyBefore,
    typed,
    sent,
    bodyPreview: result.text.slice(0, 1200)
  }
}

async function main() {
  await fs.mkdir(outDir, { recursive: true })
  const page = await target()
  const client = await connect(page.webSocketDebuggerUrl)
  const report = { ok: false, steps: [], consoleEvents: [] }

  try {
    await client.send('Runtime.enable')
    await client.send('Page.enable')
    await client.send('Page.bringToFront')
    await click(client, 'Open DASHBOARD view')
    await wait(500)
    await click(client, 'Clear transcript')

    report.steps.push(await runChartPrompt(client, 'calculate 11*11', /Result:\s*121|\b121\b/i, 'chart_calculator_tool'))
    report.steps.push(await runChartPrompt(client, 'convert 2 meter to centimeter', /200\s*cm|2\.0\s*m\s*=\s*200/i, 'chart_unit_conversion_tool'))
    report.steps.push(await runChartPrompt(client, 'hash shell with sha256', /Hash Result|sha256|ce635c4e/i, 'chart_hash_tool'))
    report.steps.push(await runChartPrompt(client, 'encode hello as base64', /aGVsbG8=|base64 encoded/i, 'chart_text_encode_tool'))
    report.steps.push(await runChartPrompt(client, 'show all tools', /Tool Registry|Total Tools|shell/i, 'chart_list_tools_route'))

    const animation = await evaluate(client, `
      (() => {
        const node = document.createElement('div')
        node.className = 'animate-in fade-in zoom-in duration-300'
        node.style.position = 'fixed'
        node.style.left = '-9999px'
        document.body.appendChild(node)
        const style = getComputedStyle(node)
        const result = {
          animationName: style.animationName,
          animationDuration: style.animationDuration,
          opacityVar: style.getPropertyValue('--shell-enter-opacity').trim(),
          scaleVar: style.getPropertyValue('--shell-enter-scale').trim()
        }
        node.remove()
        return result
      })()
    `)
    report.steps.push({
      name: 'css_enter_animation_runtime',
      ok: animation.animationName && animation.animationName !== 'none' && !/^0s/.test(animation.animationDuration),
      animation
    })

    const gallerySave = await evaluate(client, `
      window.shellAPI.call('save-image-to-gallery', {
        title: 'Probe gallery visual',
        base64Data: ${JSON.stringify(PNG_DATA_URL)}
      })
    `)
    await click(client, 'Open GALLERY view')
    const galleryText = await waitForText(client, /Probe gallery visual/i, 12000)
    const galleryImageCount = await evaluate(client, `document.querySelectorAll('img').length`)
    const artifactCountText = await bodyText(client)
    report.steps.push({
      name: 'gallery_save_and_render_bridge',
      ok: Boolean(gallerySave?.success) && galleryText.ok && galleryImageCount > 0 && !/0 ARTIFACTS/i.test(artifactCountText),
      gallerySave,
      galleryImageCount,
      bodyPreview: galleryText.text.slice(0, 1200)
    })

    report.consoleEvents = client.events.filter((event) => {
      if (event.method === 'Runtime.exceptionThrown') return true
      if (event.method !== 'Runtime.consoleAPICalled') return false
      return ['error', 'assert'].includes(String(event.params?.type || '').toLowerCase())
    })
    report.ok = report.steps.every((step) => step.ok) && report.consoleEvents.length === 0
  } finally {
    const reportPath = path.join(outDir, 'report.json')
    await fs.writeFile(reportPath, JSON.stringify(report, null, 2), 'utf8')
    client.close()
    console.log(JSON.stringify({ ok: report.ok, reportPath, steps: report.steps }, null, 2))
  }

  if (!report.ok) process.exitCode = 1
}

main().catch((error) => {
  console.error(error)
  process.exitCode = 1
})
