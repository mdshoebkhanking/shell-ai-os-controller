// SPDX-License-Identifier: Apache-2.0

import fs from 'node:fs/promises'
import path from 'node:path'

const port = Number(process.env.SHELL_WEB_UI_DEBUG_PORT || process.argv[2] || 9235)
const outDir = path.resolve(process.argv[3] || '.shell_runtime/current_ui_screens')

const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

async function getTarget() {
  const targets = await fetch(`http://127.0.0.1:${port}/json`).then((response) => response.json())
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
        }
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

async function clickByLabel(client, label) {
  return evaluate(client, `
    (() => {
      const wanted = ${JSON.stringify(label)}.toLowerCase()
      const normalize = (value) => String(value || '').trim().replace(/\\s+/g, ' ')
      const visible = (el) => {
        const rect = el.getBoundingClientRect()
        const style = getComputedStyle(el)
        return rect.width > 1 && rect.height > 1 && style.visibility !== 'hidden' && style.display !== 'none'
      }
      const candidates = Array.from(document.querySelectorAll('button,[role="button"],a,[tabindex]'))
        .filter(visible)
        .map((el) => {
          const text = normalize(el.innerText || el.textContent || '')
          const aria = normalize(el.getAttribute('aria-label') || '')
          const title = normalize(el.getAttribute('title') || '')
          const hay = [aria, title, text].filter(Boolean)
          const score = hay.some((v) => v.toLowerCase() === wanted) ? 0 :
            hay.some((v) => v.toLowerCase().includes(wanted)) ? 1 : 99
          return { el, text, aria, title, score }
        })
        .filter((item) => item.score < 99)
        .sort((a, b) => a.score - b.score)
      const candidate = candidates[0]
      if (!candidate) return { clicked: false, label: ${JSON.stringify(label)}, reason: 'not_found' }
      candidate.el.scrollIntoView({ block: 'center', inline: 'center', behavior: 'instant' })
      candidate.el.click()
      return {
        clicked: true,
        label: ${JSON.stringify(label)},
        text: candidate.text,
        aria: candidate.aria,
        title: candidate.title,
      }
    })()
  `)
}

async function capture(client, name) {
  await wait(1500)
  const response = await client.send('Page.captureScreenshot', {
    format: 'png',
    fromSurface: true,
    captureBeyondViewport: false,
  })
  const file = path.join(outDir, `${name}.png`)
  await fs.writeFile(file, Buffer.from(response.result.data, 'base64'))
  return file
}

async function main() {
  await fs.mkdir(outDir, { recursive: true })
  const target = await getTarget()
  const client = await connect(target.webSocketDebuggerUrl)
  await client.send('Runtime.enable')
  await client.send('Page.enable')
  await client.send('Log.enable')
  await client.send('Emulation.setDeviceMetricsOverride', {
    width: 1440,
    height: 900,
    deviceScaleFactor: 1,
    mobile: false,
  })
  await evaluate(client, `
    (() => {
      localStorage.setItem('shell_voice_runtime', 'backend')
      window.dispatchEvent(new Event('shell-voice-runtime-changed'))
    })()
  `)
  await wait(1200)

  const captures = []
  const sequence = [
    ['dashboard', 'Open DASHBOARD view'],
    ['macros', 'Open Macros view'],
    ['apps', 'Open Apps view'],
    ['notes', 'Open NOTES view'],
    ['gallery', 'Open GALLERY view'],
    ['phone', 'Open PHONE view'],
    ['control', 'Open CONTROL view'],
    ['settings', 'Open SETTINGS view'],
  ]

  for (const [name, label] of sequence) {
    if (label === 'Open Macros view' || label === 'Open PHONE view') {
      await clickByLabel(client, 'Open more Shell views')
      await wait(250)
    }
    const click = await clickByLabel(client, label)
    const file = await capture(client, name)
    const body = await evaluate(client, 'document.body.innerText.slice(0, 1400)')
    captures.push({ name, label, click, file, bodyPreview: body })
  }

  const report = {
    ok: true,
    port,
    outDir,
    target: { title: target.title, url: target.url },
    captures,
    consoleEvents: client.events
      .filter((event) => ['Runtime.consoleAPICalled', 'Log.entryAdded'].includes(event.method))
      .slice(-30),
  }
  await fs.writeFile(path.join(outDir, 'report.json'), JSON.stringify(report, null, 2))
  client.close()
  console.log(JSON.stringify({ ok: true, outDir, captures: captures.map((item) => ({ name: item.name, file: item.file, clicked: item.click.clicked })) }, null, 2))
}

main().catch((error) => {
  console.error(error)
  process.exitCode = 1
})
