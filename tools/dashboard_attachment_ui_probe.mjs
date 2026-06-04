import fs from 'node:fs/promises'
import path from 'node:path'

const port = Number(process.env.SHELL_WEB_UI_DEBUG_PORT || process.argv[2] || 9235)
const outDir = path.resolve(process.argv[3] || '.shell_runtime/dashboard_attachment_probe')
const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

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
    ws.onopen = () => {
      resolve({
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
      }
    }
  })
}

async function evaluate(client, expression) {
  const response = await client.send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true })
  if (response.result?.exceptionDetails) throw new Error(response.result.exceptionDetails.text || 'Runtime evaluation failed')
  return response.result.result.value
}

async function main() {
  await fs.mkdir(outDir, { recursive: true })
  const samplePath = path.join(outDir, 'sample-notes.txt')
  await fs.writeFile(samplePath, 'Shell attached file probe content. Summarize this note clearly.', 'utf8')
  const page = await target()
  const client = await connect(page.webSocketDebuggerUrl)
  try {
    await client.send('Runtime.enable')
    await client.send('Page.enable')
    await client.send('DOM.enable')
    const root = await client.send('DOM.getDocument', { depth: 1 })
    const input = await client.send('DOM.querySelector', {
      nodeId: root.result.root.nodeId,
      selector: 'input[type="file"]'
    })
    if (!input.result.nodeId) throw new Error('file input not found')
    await client.send('DOM.setFileInputFiles', { nodeId: input.result.nodeId, files: [samplePath] })
    await wait(800)
    const attached = await evaluate(
      client,
      `(() => ({ chip: document.querySelector('.shell-attachment-chip')?.innerText || '', work: document.querySelector('.shell-workstream-panel')?.innerText || '' }))()`
    )
    const typed = await evaluate(
      client,
      `
        (() => {
          const value = 'is attached file ko summarize karo'
          const input = document.querySelector('input[placeholder^="Ask Shell"], input[placeholder^="Type to Shell"]')
          const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')?.set
          setter?.call(input, value)
          input.dispatchEvent(new Event('input', { bubbles: true }))
          input.focus()
          return { typed: input.value === value, value: input.value }
        })()
      `
    )
    const button = await evaluate(
      client,
      `
        (() => {
          const input = document.querySelector('input[placeholder^="Ask Shell"], input[placeholder^="Type to Shell"]')
          const rect = input.getBoundingClientRect()
          return Array.from(document.querySelectorAll('button'))
            .filter((el) => !el.disabled)
            .map((el) => {
              const r = el.getBoundingClientRect()
              return { x: r.left + r.width / 2, y: r.top + r.height / 2, aria: el.getAttribute('aria-label') || '', text: (el.innerText || '').trim(), near: r.top >= rect.top - 8 && r.top <= rect.bottom + 8 && r.left > rect.left }
            })
            .filter((item) => /send transcript message/i.test(item.aria) || item.near)
            .sort((a, b) => (/send transcript message/i.test(b.aria) ? 1 : 0) - (/send transcript message/i.test(a.aria) ? 1 : 0) || a.x - b.x)[0] || null
        })()
      `
    )
    if (!button) throw new Error('send button not found')
    await client.send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: button.x, y: button.y, button: 'none' })
    await client.send('Input.dispatchMouseEvent', { type: 'mousePressed', x: button.x, y: button.y, button: 'left', clickCount: 1 })
    await client.send('Input.dispatchMouseEvent', { type: 'mouseReleased', x: button.x, y: button.y, button: 'left', clickCount: 1 })
    await wait(1200)
    const after = await evaluate(client, `document.body.innerText || ''`)
    const report = {
      ok: /sample-notes\.txt/i.test(attached.chip) && typed.typed && /Attached: sample-notes\.txt/i.test(after),
      attached,
      typed,
      bodyPreview: after.slice(0, 2200)
    }
    await fs.writeFile(path.join(outDir, 'report.json'), JSON.stringify(report, null, 2))
    console.log(JSON.stringify(report, null, 2))
  } finally {
    client.close()
  }
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})
