import fs from 'node:fs/promises'
import path from 'node:path'

const port = Number(process.env.SHELL_WEB_UI_DEBUG_PORT || process.argv[2] || 9235)
const outDir = path.resolve(process.argv[3] || '.shell_runtime/chart_transcript_ui_probe')
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

async function screenshot(client, name) {
  const response = await client.send('Page.captureScreenshot', { format: 'png', fromSurface: true })
  const file = path.join(outDir, `${name}.png`)
  await fs.writeFile(file, Buffer.from(response.result.data, 'base64'))
  return file
}

async function click(client, label) {
  const rect = await evaluate(client, `
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
  return evaluate(client, `
    (() => {
      const input = document.querySelector('input[placeholder^="Type to Shell"]')
      if (!input) return { typed: false, reason: 'input_not_found' }
      const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')?.set
      setter?.call(input, ${JSON.stringify(value)})
      input.dispatchEvent(new Event('input', { bubbles: true }))
      input.focus()
      return { typed: input.value === ${JSON.stringify(value)}, value: input.value }
    })()
  `)
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

async function runChartQuestion(client, prompt, expected, notExpected, name) {
  const typed = await setPrompt(client, prompt)
  await wait(100)
  const sent = await click(client, 'Send chart prompt')
  const result = await waitForText(client, expected)
  const text = result.text
  return {
    name,
    ok: typed.typed && sent.clicked && result.ok && !(notExpected && notExpected.test(text)),
    typed,
    sent,
    bodyPreview: text.slice(0, 1600),
    screenshot: await screenshot(client, name)
  }
}

async function main() {
  await fs.mkdir(outDir, { recursive: true })
  const page = await target()
  const client = await connect(page.webSocketDebuggerUrl)
  const report = { ok: false, steps: [], screenshots: {}, consoleEvents: [] }

  try {
    await client.send('Runtime.enable')
    await client.send('Page.enable')
    await client.send('Page.bringToFront')
    await client.send('Runtime.evaluate', {
      expression: `
        (() => {
          window.__shellVoiceProbe = { speechSpeak: 0, ipcSpeak: 0, shellSpeakText: 0 }
          const synth = window.speechSynthesis
          if (synth && !synth.__shellChartProbeWrapped) {
            const originalSpeak = synth.speak.bind(synth)
            synth.speak = (utterance) => {
              window.__shellVoiceProbe.speechSpeak += 1
              return originalSpeak(utterance)
            }
            synth.__shellChartProbeWrapped = true
          }
          if (window.electron?.ipcRenderer && !window.electron.ipcRenderer.__shellChartProbeWrapped) {
            const originalInvoke = window.electron.ipcRenderer.invoke.bind(window.electron.ipcRenderer)
            window.electron.ipcRenderer.invoke = (channel, ...args) => {
              if (channel === 'speak-text') window.__shellVoiceProbe.ipcSpeak += 1
              return originalInvoke(channel, ...args)
            }
            window.electron.ipcRenderer.__shellChartProbeWrapped = true
          }
        })()
      `
    })
    await click(client, 'Open DASHBOARD view')
    await wait(600)

    const clear1 = await click(client, 'Clear transcript')
    const cleared = await waitForText(client, /No Data Stream/i, 4000)
    report.steps.push({
      name: 'transcript_clear_button',
      ok: clear1.clicked && !/Result:\s*4|Chart: network|Shell ne message receive/i.test(cleared.text),
      click: clear1,
      bodyPreview: cleared.text.slice(0, 1000),
      screenshot: await screenshot(client, 'transcript_clear_button')
    })

    report.steps.push(
      await runChartQuestion(
        client,
        'what is memory in Python?',
        /Memory in Python|Python memory|heap|garbage collector|reference counting/i,
        /Chart:\s*RAM/i,
        'chart_normal_python_memory_question'
      )
    )
    report.steps.push(
      await runChartQuestion(
        client,
        'explain network protocols',
        /Network protocol|TCP\/IP|HTTP|DNS|data exchange|devices/i,
        /Chart:\s*network/i,
        'chart_normal_network_question'
      )
    )
    report.steps.push(
      await runChartQuestion(
        client,
        'show CPU chart',
        /Chart:\s*CPU|CORE METRICS/i,
        null,
        'chart_explicit_cpu_chart'
      )
    )
    report.steps.push(
      await runChartQuestion(
        client,
        'calculate 7*6',
        /Result:\s*42|\b42\b/i,
        null,
        'chart_command_route_calculator'
      )
    )
    report.steps.push(
      await runChartQuestion(
        client,
        'tumhe yaad hai maine abhi kya kaam diya tha?',
        /Tumne pichla kaam bola tha:\s*"calculate 7\*6"|pichla kaam.*calculate 7\*6/i,
        /koi pehla chart ya command task saved nahi mila/i,
        'chart_context_recall_previous_task'
      )
    )

    const voiceProbe = await evaluate(client, `window.__shellVoiceProbe || { speechSpeak: 0, ipcSpeak: 0, shellSpeakText: 0 }`)
    const terminalHiddenText = await bodyText(client)
    report.steps.push({
      name: 'chart_text_mode_no_voice_and_no_hidden_terminal',
      ok:
        voiceProbe.speechSpeak === 0 &&
        voiceProbe.ipcSpeak === 0 &&
        voiceProbe.shellSpeakText === 0 &&
        !/SHELL TERMINAL|SYSTEM CORE: ONLINE|PID:\s*8094/i.test(terminalHiddenText),
      voiceProbe,
      bodyPreview: terminalHiddenText.slice(0, 1200)
    })

    const clearFinal = await click(client, 'Clear transcript')
    await wait(800)
    const finalText = await bodyText(client)
    report.steps.push({
      name: 'transcript_clear_after_messages',
      ok: clearFinal.clicked && !/what is memory in Python|explain network protocols|calculate 7\*6|Result:\s*42|tumhe yaad hai/i.test(finalText),
      click: clearFinal,
      bodyPreview: finalText.slice(0, 1000),
      screenshot: await screenshot(client, 'transcript_clear_after_messages')
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
