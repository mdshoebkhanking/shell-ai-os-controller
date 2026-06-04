import fs from 'node:fs/promises'
import path from 'node:path'

const port = Number(process.env.SHELL_WEB_UI_DEBUG_PORT || process.argv[2] || 9235)
const outDir = path.resolve(process.argv[3] || '.shell_runtime/dashboard_image_generation_probe')
const prompt = process.argv.slice(4).join(' ') || 'simple shell ai dashboard icon image generate karo'
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

async function screenshot(client, name) {
  const response = await client.send('Page.captureScreenshot', { format: 'png', fromSurface: true })
  const file = path.join(outDir, `${name}.png`)
  await fs.writeFile(file, Buffer.from(response.result.data, 'base64'))
  return file
}

async function setPrompt(client, value) {
  return evaluate(
    client,
    `
      (() => {
        const input = document.querySelector('input[placeholder^="Type to Shell"]')
        if (!input) return { typed: false, reason: 'input_not_found' }
        const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')?.set
        setter?.call(input, ${JSON.stringify(value)})
        input.dispatchEvent(new Event('input', { bubbles: true }))
        input.focus()
        return { typed: input.value === ${JSON.stringify(value)}, value: input.value }
      })()
    `
  )
}

async function clickSend(client) {
  const rect = await evaluate(
    client,
    `
      (() => {
        const input = document.querySelector('input[placeholder^="Type to Shell"]')
        if (!input) return null
        const inputRect = input.getBoundingClientRect()
        const visible = (el) => {
          const rect = el.getBoundingClientRect()
          const style = getComputedStyle(el)
          return rect.width > 1 && rect.height > 1 && style.display !== 'none' && style.visibility !== 'hidden'
        }
        const buttons = Array.from(document.querySelectorAll('button'))
          .filter((el) => visible(el) && !el.disabled)
          .map((el) => {
            const rect = el.getBoundingClientRect()
            const text = String(el.innerText || el.textContent || '').trim().replace(/\\s+/g, ' ')
            const aria = String(el.getAttribute('aria-label') || '').trim()
            const score =
              /send transcript message/i.test(aria) ? 0 :
                rect.top >= inputRect.top - 8 && rect.top <= inputRect.bottom + 8 && rect.left > inputRect.left ? 1 : 99
            return { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2, text, aria, score }
          })
          .filter((item) => item.score < 99)
          .sort((a, b) => a.score - b.score || a.x - b.x)
        return buttons[0] || null
      })()
    `
  )
  if (!rect) return { clicked: false, reason: 'send_not_found' }
  await client.send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: rect.x, y: rect.y, button: 'none' })
  await client.send('Input.dispatchMouseEvent', { type: 'mousePressed', x: rect.x, y: rect.y, button: 'left', clickCount: 1 })
  await client.send('Input.dispatchMouseEvent', { type: 'mouseReleased', x: rect.x, y: rect.y, button: 'left', clickCount: 1 })
  return { clicked: true, text: rect.text, aria: rect.aria, x: Math.round(rect.x), y: Math.round(rect.y) }
}

async function main() {
  await fs.mkdir(outDir, { recursive: true })
  const page = await target()
  const client = await connect(page.webSocketDebuggerUrl)
  try {
    await client.send('Runtime.enable')
    await client.send('Page.enable')
    const before = await evaluate(
      client,
      `(() => ({ work: document.querySelector('.shell-workstream-panel')?.innerText || '', hasInput: Boolean(document.querySelector('input[placeholder^="Type to Shell"]')) }))()`
    )
    const typed = await setPrompt(client, prompt)
    await wait(100)
    const sent = await clickSend(client)
    let latest = {}
    for (let index = 0; index < 180; index += 1) {
      await wait(500)
      latest = await evaluate(
        client,
        `
          (() => ({
            work: document.querySelector('.shell-workstream-panel')?.innerText || '',
            body: document.body.innerText || ''
          }))()
        `
      )
      const body = String(latest.body || '')
      const work = String(latest.work || '')
      if (
        /Image Generated|Image generate nahi ho payi|Image generation failed|📂|Saved|Gallery/i.test(body) ||
        /IMAGE GENERATION[\\s\\S]*(TASK COMPLETE|TASK FAILED)/i.test(work)
      ) {
        break
      }
    }
    const screenshotPath = await screenshot(client, 'image-generation')
    const body = String(latest.body || '')
    const work = String(latest.work || '')
    const marker = `YOU\n${prompt}\nSHELL\n`
    const markerIndex = body.lastIndexOf(marker)
    const latestReply = markerIndex >= 0 ? body.slice(markerIndex + marker.length) : body.slice(-2600)
    const ok = (
      /Image Generated|Image generated|📂|Saved|Gallery|save ho gayi/i.test(latestReply) ||
      /IMAGE GENERATION[\s\S]*(TASK COMPLETE)/i.test(work)
    ) && !/Image generation failed|Image generate nahi ho payi/i.test(latestReply)
    const report = {
      ok,
      prompt,
      before,
      typed,
      sent,
      work,
      latestReplyPreview: latestReply.slice(0, 1800),
      screenshot: screenshotPath
    }
    await fs.writeFile(path.join(outDir, 'report.json'), JSON.stringify(report, null, 2))
    console.log(JSON.stringify(report, null, 2))
    if (!ok) process.exitCode = 1
  } finally {
    client.close()
  }
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})
