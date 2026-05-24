import fs from 'node:fs/promises'
import path from 'node:path'

const port = Number(process.env.SHELL_WEB_UI_DEBUG_PORT || process.argv[2] || 9223)
const outDir = path.resolve(process.argv[3] || '.shell_runtime/real_web_ui_cdp_probe')

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

function targetRectExpression(label) {
  return `
  (() => {
    const target = ${JSON.stringify(label)}.toLowerCase()
    const normalize = (text) => String(text || '').trim().replace(/\\s+/g, ' ')
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
        const haystacks = [aria, text].filter(Boolean)
        const score = haystacks.some((value) => value.toLowerCase() === target) ? 0 :
          haystacks.some((value) => value.toLowerCase().startsWith(target)) ? 1 :
          haystacks.some((value) => value.toLowerCase().includes(target)) ? 2 : 99
        const rect = el.getBoundingClientRect()
        return {
          text,
          aria,
          score,
          x: rect.left + rect.width / 2,
          y: rect.top + rect.height / 2,
          width: rect.width,
          height: rect.height
        }
      })
      .filter((item) => item.score < 99)
      .sort((a, b) => a.score - b.score || (a.width * a.height) - (b.width * b.height))
    return candidates[0] || null
  })()
  `
}

async function scrollTargetIntoView(client, label) {
  return evaluate(client, `
    (() => {
      const target = ${JSON.stringify(label)}.toLowerCase()
      const normalize = (text) => String(text || '').trim().replace(/\\s+/g, ' ')
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
          const haystacks = [aria, text].filter(Boolean)
          const score = haystacks.some((value) => value.toLowerCase() === target) ? 0 :
            haystacks.some((value) => value.toLowerCase().startsWith(target)) ? 1 :
            haystacks.some((value) => value.toLowerCase().includes(target)) ? 2 : 99
          return { el, score, text, aria }
        })
        .filter((item) => item.score < 99)
        .sort((a, b) => a.score - b.score)
      const candidate = candidates[0]
      if (!candidate) return { scrolled: false, label: ${JSON.stringify(label)}, reason: 'not_found' }
      candidate.el.scrollIntoView({ block: 'center', inline: 'center', behavior: 'instant' })
      return { scrolled: true, label: ${JSON.stringify(label)}, text: candidate.text, aria: candidate.aria }
    })()
  `)
}

async function clickTarget(client, label) {
  const rect = await evaluate(client, targetRectExpression(label))
  if (!rect) return { clicked: false, label, reason: 'not_found' }
  await client.send('Input.dispatchMouseEvent', {
    type: 'mouseMoved',
    x: rect.x,
    y: rect.y,
    button: 'none'
  })
  await client.send('Input.dispatchMouseEvent', {
    type: 'mousePressed',
    x: rect.x,
    y: rect.y,
    button: 'left',
    clickCount: 1
  })
  await client.send('Input.dispatchMouseEvent', {
    type: 'mouseReleased',
    x: rect.x,
    y: rect.y,
    button: 'left',
    clickCount: 1
  })
  return { clicked: true, label, text: rect.text, aria: rect.aria, x: Math.round(rect.x), y: Math.round(rect.y) }
}

function placeholderRectExpression(placeholder) {
  return `
  (() => {
    const el = document.querySelector(${JSON.stringify(`[placeholder="${placeholder}"]`)})
    if (!el) return null
    const rect = el.getBoundingClientRect()
    return { x: rect.left + 20, y: rect.top + Math.min(20, rect.height / 2), width: rect.width, height: rect.height }
  })()
  `
}

async function typeIntoPlaceholder(client, placeholder, text) {
  const rect = await evaluate(client, placeholderRectExpression(placeholder))
  if (!rect) return { typed: false, placeholder, reason: 'not_found' }
  await client.send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: rect.x, y: rect.y, button: 'none' })
  await client.send('Input.dispatchMouseEvent', { type: 'mousePressed', x: rect.x, y: rect.y, button: 'left', clickCount: 1 })
  await client.send('Input.dispatchMouseEvent', { type: 'mouseReleased', x: rect.x, y: rect.y, button: 'left', clickCount: 1 })
  await client.send('Input.insertText', { text })
  return { typed: true, placeholder, x: Math.round(rect.x), y: Math.round(rect.y), chars: text.length }
}

async function replaceFirstTextarea(client, text) {
  const focusResult = await evaluate(client, `
    (() => {
      const textarea = document.querySelector('textarea')
      if (!textarea) return { typed: false, reason: 'textarea_not_found' }
      textarea.scrollIntoView({ block: 'center', inline: 'nearest', behavior: 'instant' })
      textarea.focus()
      textarea.select()
      const rect = textarea.getBoundingClientRect()
      return {
        typed: true,
        x: rect.left + Math.min(20, rect.width / 2),
        y: rect.top + Math.min(20, rect.height / 2)
      }
    })()
  `)
  if (!focusResult?.typed) return focusResult
  await client.send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: focusResult.x, y: focusResult.y, button: 'none' })
  await client.send('Input.dispatchMouseEvent', { type: 'mousePressed', x: focusResult.x, y: focusResult.y, button: 'left', clickCount: 1 })
  await client.send('Input.dispatchMouseEvent', { type: 'mouseReleased', x: focusResult.x, y: focusResult.y, button: 'left', clickCount: 1 })
  await evaluate(client, `document.querySelector('textarea')?.select()`)
  await client.send('Input.insertText', { text })
  await wait(150)
  const domValue = await evaluate(client, `document.querySelector('textarea')?.value || ''`)
  return { typed: domValue === text, chars: text.length, domValue }
}

async function setPhoneInputs(client, ip, portValue) {
  return evaluate(client, `
    (() => {
      const inputs = Array.from(document.querySelectorAll('input'))
      const setValue = (input, value) => {
        const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')?.set
        setter?.call(input, value)
        input.dispatchEvent(new Event('input', { bubbles: true }))
      }
      const ipInput = inputs.find((input) => input.placeholder === '192.168.1.xxx')
      const portInput = inputs.find((input) => input.placeholder === '5555')
      if (!ipInput || !portInput) return { typed: false, reason: 'phone_inputs_not_found' }
      setValue(ipInput, ${JSON.stringify(ip)})
      setValue(portInput, ${JSON.stringify(portValue)})
      return { typed: true, ip: ipInput.value, port: portInput.value }
    })()
  `)
}

const pageSummaryExpression = `
(() => {
  const visible = (el) => {
    const rect = el.getBoundingClientRect()
    const style = getComputedStyle(el)
    return rect.width > 1 && rect.height > 1 && style.visibility !== 'hidden' && style.display !== 'none'
  }
  const controls = Array.from(document.querySelectorAll('button,[role="button"],a,[tabindex]'))
    .filter(visible)
    .map((el, index) => ({
      index,
      tag: el.tagName,
      text: (el.innerText || el.textContent || el.getAttribute('aria-label') || '').trim().replace(/\\s+/g, ' ').slice(0, 120),
      className: String(el.className || '').slice(0, 160),
      aria: el.getAttribute('aria-label') || ''
    }))
  return {
    title: document.title,
    url: location.href,
    bodyText: document.body.innerText.slice(0, 2500),
    controlCount: controls.length,
    controls
  }
})()
`

async function main() {
  await fs.mkdir(outDir, { recursive: true })
  const target = await getTarget()
  const client = await connect(target.webSocketDebuggerUrl)
  const report = {
    ok: true,
    target: { title: target.title, url: target.url },
    screenshots: {},
    steps: [],
    console: []
  }

  client.events.length = 0
  await client.send('Runtime.enable')
  await client.send('Page.enable')
  await client.send('Log.enable')
  await evaluate(client, `
    (() => {
      localStorage.setItem('shell_voice_runtime', 'backend')
      window.dispatchEvent(new Event('shell-voice-runtime-changed'))
    })()
  `)
  await wait(800)

  const initial = await evaluate(client, pageSummaryExpression)
  report.steps.push({
    name: 'initial_dashboard',
    ok: initial.bodyText.includes('Shell AI') && initial.bodyText.includes('DASHBOARD'),
    controlCount: initial.controlCount,
    controls: initial.controls
  })
  report.screenshots.initial_dashboard = await screenshot(client, '01_initial_dashboard')
  report.steps.push({
    name: 'topbar_no_center_title_clutter',
    ok: !initial.bodyText.includes('Shell OS //') && !initial.bodyText.includes('MAC/SYSTEM'),
    bodyPreview: initial.bodyText.slice(0, 500)
  })
  const logoProbe = await evaluate(client, `
    (() => {
      const logo = document.querySelector('img[alt="Shell AI"]')
      return {
        found: Boolean(logo),
        naturalWidth: logo?.naturalWidth || 0,
        naturalHeight: logo?.naturalHeight || 0,
        src: logo?.getAttribute('src') || ''
      }
    })()
  `)
  report.steps.push({
    name: 'shell_logo_loaded',
    ok: Boolean(logoProbe.found && logoProbe.naturalWidth > 0 && logoProbe.naturalHeight > 0),
    probe: logoProbe
  })

  const tabs = [
    ['Open DASHBOARD view', 'DASHBOARD', ['TRANSCRIPT', 'CORE METRICS']],
    ['Open Macros view', 'macros', ['Neural', 'Patterns', 'MODULE LIBRARY']],
    ['Open Apps view', 'apps', ['FOUND', 'INDEXING', 'INSTALLED']],
    ['Open NOTES view', 'notes', ['ITEMS', 'Memory', 'NOTE']],
    ['Open GALLERY view', 'gallery', ['ARTIFACTS', 'Visual', 'Gallery']],
    ['Open PHONE view', 'phone', ['PHONE', 'DEVICE', 'ARCHIVE']],
    ['Open CONTROL view', 'control', ['BACKEND CONTROL', 'PARAMETERS JSON', 'EXECUTE']],
    ['Open SETTINGS view', 'settings', ['SETTINGS', 'PERSONALITY', 'Vault', 'Command Center']]
  ]

  for (const [targetLabel, reportLabel, expected] of tabs) {
    const click = await clickTarget(client, targetLabel)
    await wait(900)
    const summary = await evaluate(client, pageSummaryExpression)
    const body = summary.bodyText
    const ok = click.clicked && expected.some((token) => body.toLowerCase().includes(String(token).toLowerCase()))
    const safeName = String(reportLabel).toLowerCase().replace(/[^a-z0-9]+/g, '_')
    report.screenshots[safeName] = await screenshot(client, `tab_${safeName}`)
    report.steps.push({
      name: `tab_${reportLabel}`,
      ok,
      click,
      expected,
      bodyPreview: body.slice(0, 900),
      controlCount: summary.controlCount
    })
  }

  await clickTarget(client, 'Open SETTINGS view')
  await wait(600)
  const settingsTabs = [
    ['Open settings system tab', 'settings_system', ['OS Firmware', 'Patch Notes']],
    ['Open settings general tab', 'settings_general', ['Voice Profile', 'Personality', 'Designation']],
    ['Open settings api keys tab', 'settings_api_keys', ['External API Endpoints', 'Gemini', 'Groq']],
    ['Open settings security tab', 'settings_security', ['Security', 'Master', 'PIN']]
  ]
  for (const [targetLabel, reportLabel, expected] of settingsTabs) {
    const click = await clickTarget(client, targetLabel)
    await wait(500)
    const summary = await evaluate(client, pageSummaryExpression)
    const body = summary.bodyText
    const ok = click.clicked && expected.some((token) => body.toLowerCase().includes(String(token).toLowerCase()))
    report.screenshots[reportLabel] = await screenshot(client, reportLabel)
    report.steps.push({
      name: reportLabel,
      ok,
      click,
      expected,
      bodyPreview: body.slice(0, 900)
    })

    if (reportLabel === 'settings_general') {
      const scrollProbe = await evaluate(client, `
        (() => {
          const hasGeneralContent = document.body.innerText.includes('AI Personality Matrix') &&
            document.body.innerText.includes('OS Voice Profile')
          const scrollables = Array.from(document.querySelectorAll('div'))
            .filter((el) => {
              const style = getComputedStyle(el)
              const rect = el.getBoundingClientRect()
              return rect.height > 120 && ['auto', 'scroll'].includes(style.overflowY)
            })
            .map((el) => ({
              text: (el.innerText || '').slice(0, 240),
              scrollHeight: el.scrollHeight,
              clientHeight: el.clientHeight,
              canScroll: el.scrollHeight > el.clientHeight + 2
            }))
          const relevant = scrollables.find((item) =>
            item.text.includes('AI Personality Matrix') || item.text.includes('OS Voice Profile')
          )
          if (relevant?.canScroll) {
            const container = Array.from(document.querySelectorAll('div')).find((el) => {
              const style = getComputedStyle(el)
              return ['auto', 'scroll'].includes(style.overflowY) &&
                (el.innerText || '').includes('OS Voice Profile')
            })
            if (container) container.scrollTop = container.scrollHeight
          }
          return { hasGeneralContent, relevant: relevant || null, scrollables: scrollables.slice(0, 8) }
        })()
      `)
      await wait(200)
      report.steps.push({
        name: 'settings_general_scroll_available',
        ok: Boolean(scrollProbe.hasGeneralContent && scrollProbe.relevant),
        probe: scrollProbe
      })
    }

    if (reportLabel === 'settings_api_keys') {
      const apiScrollProbe = await evaluate(client, `
        (() => {
          const normalize = (text) => String(text || '').replace(/\\s+/g, ' ').trim()
          const body = normalize(document.body.innerText).toLowerCase()
          const hasApiContent = body.includes('external api endpoints') &&
            (body.includes('openweather') || body.includes('weather key') || body.includes('search engine id'))
          const divs = Array.from(document.querySelectorAll('div'))
          const scrollables = divs
            .filter((el) => {
              const style = getComputedStyle(el)
              const rect = el.getBoundingClientRect()
              return rect.height > 120 && ['auto', 'scroll'].includes(style.overflowY)
            })
            .map((el) => ({
              text: normalize(el.innerText).slice(0, 520),
              scrollHeight: el.scrollHeight,
              clientHeight: el.clientHeight,
              canScroll: el.scrollHeight > el.clientHeight + 2,
              top: Math.round(el.getBoundingClientRect().top)
            }))
          const relevant = scrollables.find((item) =>
            item.text.includes('External API Endpoints') || item.text.includes('OpenWeather') || item.text.includes('Gemini')
          )
          const container = divs.find((el) => {
            const style = getComputedStyle(el)
            const text = normalize(el.innerText)
            return ['auto', 'scroll'].includes(style.overflowY) &&
              text.includes('External API Endpoints') &&
              el.scrollHeight > el.clientHeight + 2
          })
          if (container) container.scrollTop = container.scrollHeight
          const afterText = normalize(container?.innerText || document.body.innerText)
          const bottomVisible = /OpenWeather|Weather Key|Search Engine ID/i.test(afterText)
          return {
            hasApiContent,
            bottomVisible,
            relevant: relevant || null,
            scrolledTo: container ? Math.round(container.scrollTop) : 0,
            scrollables: scrollables.slice(0, 8)
          }
        })()
      `)
      report.steps.push({
        name: 'settings_api_keys_scroll_available',
        ok: Boolean(apiScrollProbe.relevant?.canScroll && (apiScrollProbe.hasApiContent || apiScrollProbe.bottomVisible)),
        probe: apiScrollProbe
      })

      const telegramScroll = await scrollTargetIntoView(client, 'Check Telegram bot status')
      await wait(200)
      const telegramStatusClick = await clickTarget(client, 'Check Telegram bot status')
      await wait(900)
      const telegramSummary = await evaluate(client, pageSummaryExpression)
      report.screenshots.settings_telegram_status = await screenshot(client, 'settings_telegram_status')
      report.steps.push({
        name: 'settings_telegram_status_panel',
        ok:
          telegramScroll.scrolled &&
          telegramStatusClick.clicked &&
          /Telegram Bot|Token:|PC control/i.test(telegramSummary.bodyText),
        click: telegramStatusClick,
        scroll: telegramScroll,
        bodyPreview: telegramSummary.bodyText.slice(0, 1400)
      })
    }
  }

  await clickTarget(client, 'Open CONTROL view')
  await wait(900)
  const controlSearchTyping = await typeIntoPlaceholder(client, 'Search tools, agents, actions...', 'calculator')
  await wait(500)
  const calculatorToolClick = await clickTarget(client, 'shell_calculator:calculate_tool')
  await wait(300)
  const controlArgsTyping = await replaceFirstTextarea(client, JSON.stringify({ expression: '2+2' }, null, 2))
  const executeToolClick = await clickTarget(client, 'Execute selected backend tool')
  await wait(1600)
  const controlSummary = await evaluate(client, pageSummaryExpression)
  report.screenshots.control_calculator_execute = await screenshot(client, 'control_calculator_execute')
  report.steps.push({
    name: 'control_center_calculator_execute',
    ok:
      controlSearchTyping.typed &&
      calculatorToolClick.clicked &&
      controlArgsTyping.typed &&
      executeToolClick.clicked &&
      /shell_calculator:calculate_tool|calculate_tool/i.test(controlSummary.bodyText) &&
      /\\b4\\b|Result:/i.test(controlSummary.bodyText),
    click: { calculatorToolClick, executeToolClick },
    fill: { controlSearchTyping, controlArgsTyping },
    bodyPreview: controlSummary.bodyText.slice(0, 1600)
  })

  await clickTarget(client, 'Open PHONE view')
  await wait(700)
  const newDeviceClick = await clickTarget(client, 'NEW DEVICE')
  await wait(400)
  const phoneInputFill = await setPhoneInputs(client, '127.0.0.1', '1')
  const phoneConnectClick = await clickTarget(client, 'ESTABLISH CONNECTION')
  await wait(900)
  const phoneSummary = await evaluate(client, pageSummaryExpression)
  report.screenshots.phone_manual_error_state = await screenshot(client, 'phone_manual_error_state')
  report.steps.push({
    name: 'phone_manual_connect_error_state',
    ok:
      newDeviceClick.clicked &&
      phoneInputFill.typed &&
      phoneConnectClick.clicked &&
      /Connection refused|Electron IPC Error|IP and Port are required/i.test(phoneSummary.bodyText),
    click: { newDeviceClick, phoneConnectClick },
    fill: phoneInputFill,
    bodyPreview: phoneSummary.bodyText.slice(0, 1200)
  })

  await clickTarget(client, 'Open NOTES view')
  await wait(600)
  const createNoteClick = await clickTarget(client, 'Create manual note')
  await wait(300)
  const titleTyping = await typeIntoPlaceholder(client, 'ENTER NOTE TITLE...', 'Real UI Probe')
  await wait(150)
  const contentTyping = await typeIntoPlaceholder(client, 'Write your note in Markdown...', 'Created from visible Shell UI test.')
  const noteFill = { filled: titleTyping.typed && contentTyping.typed, titleTyping, contentTyping }
  await wait(300)
  report.screenshots.notes_editor = await screenshot(client, 'notes_editor')
  const saveNoteClick = await clickTarget(client, 'Save note to memory')
  await wait(1200)
  const noteSummary = await evaluate(client, pageSummaryExpression)
  const noteOk = createNoteClick.clicked && noteFill.filled && saveNoteClick.clicked && noteSummary.bodyText.toLowerCase().includes('real ui probe')
  report.screenshots.notes_saved = await screenshot(client, 'notes_saved')
  report.steps.push({
    name: 'notes_create_save',
    ok: noteOk,
    click: { createNoteClick, saveNoteClick },
    fill: noteFill,
    bodyPreview: noteSummary.bodyText.slice(0, 900)
  })

  await clickTarget(client, 'Open DASHBOARD view')
  await wait(600)
  await evaluate(client, `
    (() => {
      window.__shellVoiceProbe = { speechSpeak: 0, ipcSpeak: 0, shellSpeakText: 0 }
      const synth = window.speechSynthesis
      if (synth && !synth.__shellProbeWrapped) {
        const originalSpeak = synth.speak.bind(synth)
        synth.speak = (utterance) => {
          window.__shellVoiceProbe.speechSpeak += 1
          return originalSpeak(utterance)
        }
        synth.__shellProbeWrapped = true
      }
      if (window.electron?.ipcRenderer && !window.electron.ipcRenderer.__shellProbeWrapped) {
        const originalInvoke = window.electron.ipcRenderer.invoke.bind(window.electron.ipcRenderer)
        window.electron.ipcRenderer.invoke = (channel, ...args) => {
          if (channel === 'speak-text') window.__shellVoiceProbe.ipcSpeak += 1
          return originalInvoke(channel, ...args)
        }
        window.electron.ipcRenderer.__shellProbeWrapped = true
      }
      if (window.shellAPI && !window.shellAPI.__shellProbeWrapped) {
        const originalSpeakText = window.shellAPI.speakText?.bind(window.shellAPI)
        if (originalSpeakText) {
          window.shellAPI.speakText = (text) => {
            window.__shellVoiceProbe.shellSpeakText += 1
            return originalSpeakText(text)
          }
        }
        window.shellAPI.__shellProbeWrapped = true
      }
    })()
  `)
  const chartTyping = await typeIntoPlaceholder(client, 'Type to Shell, or ask chart about CPU/RAM/network...', 'network latency')
  await wait(150)
  const chartSend = await clickTarget(client, 'Send chart prompt')
  await wait(1000)
  const chartSummary = await evaluate(client, pageSummaryExpression)
  const chartVoiceProbe = await evaluate(client, `window.__shellVoiceProbe || { speechSpeak: 0, ipcSpeak: 0, shellSpeakText: 0 }`)
  report.screenshots.dashboard_chart_prompt = await screenshot(client, 'dashboard_chart_prompt')
  report.steps.push({
    name: 'dashboard_chart_prompt',
    ok:
      chartTyping.typed &&
      chartSend.clicked &&
      chartSummary.bodyText.includes('NETWORK TELEMETRY') &&
      chartSummary.bodyText.toLowerCase().includes('chart: network') &&
      chartVoiceProbe.speechSpeak === 0 &&
      chartVoiceProbe.ipcSpeak === 0 &&
      chartVoiceProbe.shellSpeakText === 0,
    click: chartSend,
    fill: chartTyping,
    voiceProbe: chartVoiceProbe,
    bodyPreview: chartSummary.bodyText.slice(0, 900)
  })

  const chartCommandTyping = await typeIntoPlaceholder(client, 'Type to Shell, or ask chart about CPU/RAM/network...', 'calculate 2+2')
  await wait(150)
  const chartCommandSend = await clickTarget(client, 'Send chart prompt')
  await wait(1200)
  const chartCommandSummary = await evaluate(client, pageSummaryExpression)
  const chartCommandVoiceProbe = await evaluate(client, `window.__shellVoiceProbe || { speechSpeak: 0, ipcSpeak: 0, shellSpeakText: 0 }`)
  report.steps.push({
    name: 'dashboard_chart_text_command_route',
    ok:
      chartCommandTyping.typed &&
      chartCommandSend.clicked &&
      chartCommandSummary.bodyText.toLowerCase().includes('calculate 2+2') &&
      /result:\s*4\b|\b4\b/i.test(chartCommandSummary.bodyText) &&
      chartCommandVoiceProbe.speechSpeak === 0 &&
      chartCommandVoiceProbe.ipcSpeak === 0 &&
      chartCommandVoiceProbe.shellSpeakText === 0,
    click: chartCommandSend,
    fill: chartCommandTyping,
    voiceProbe: chartCommandVoiceProbe,
    bodyPreview: chartCommandSummary.bodyText.slice(0, 1200)
  })

  const visionModalClick = await clickTarget(client, 'Toggle vision source')
  await wait(400)
  const visionSummary = await evaluate(client, pageSummaryExpression)
  report.screenshots.dashboard_vision_modal = await screenshot(client, 'dashboard_vision_modal')
  report.steps.push({
    name: 'dashboard_vision_source_modal',
    ok:
      visionModalClick.clicked &&
      visionSummary.bodyText.includes('CAMERA FEED') &&
      visionSummary.bodyText.includes('SCREEN SHARE'),
    click: visionModalClick,
    bodyPreview: visionSummary.bodyText.slice(0, 900)
  })
  await clickTarget(client, 'Close vision source selector')
  await wait(250)

  await evaluate(client, `
    (() => {
      const makeFakeStream = () => {
        const canvas = document.createElement('canvas')
        canvas.width = 320
        canvas.height = 180
        const context = canvas.getContext('2d')
        let frame = 0
        const paint = () => {
          frame += 1
          context.fillStyle = frame % 2 ? '#001f14' : '#020617'
          context.fillRect(0, 0, canvas.width, canvas.height)
          context.fillStyle = '#34d399'
          context.fillRect(20 + (frame % 40), 40, 120, 60)
        }
        paint()
        const interval = setInterval(paint, 120)
        const stream = canvas.captureStream(8)
        stream.getTracks().forEach((track) => {
          const originalStop = track.stop.bind(track)
          track.stop = () => {
            clearInterval(interval)
            originalStop()
          }
        })
        return stream
      }
      Object.defineProperty(navigator.mediaDevices, 'getUserMedia', {
        configurable: true,
        value: async () => makeFakeStream()
      })
      Object.defineProperty(navigator.mediaDevices, 'getDisplayMedia', {
        configurable: true,
        value: async () => makeFakeStream()
      })
      window.__shellFakeMediaInstalled = true
    })()
  `)
  const cameraModalClick = await clickTarget(client, 'Toggle vision source')
  await wait(200)
  const cameraFeedClick = await clickTarget(client, 'CAMERA FEED')
  await wait(700)
  const cameraSummary = await evaluate(client, pageSummaryExpression)
  const cameraOk = cameraModalClick.clicked && cameraFeedClick.clicked && cameraSummary.bodyText.includes('OPTICAL FEED')
  report.steps.push({
    name: 'dashboard_camera_fake_stream',
    ok: cameraOk,
    click: { cameraModalClick, cameraFeedClick },
    bodyPreview: cameraSummary.bodyText.slice(0, 900)
  })
  const screenModalClick = await clickTarget(client, 'Toggle vision source')
  await wait(200)
  const screenSwitchClick = await clickTarget(client, 'SCREEN SHARE')
  await wait(700)
  const screenSummary = await evaluate(client, pageSummaryExpression)
  report.steps.push({
    name: 'dashboard_screen_fake_stream',
    ok: screenModalClick.clicked && screenSwitchClick.clicked && screenSummary.bodyText.includes('SCREEN FEED'),
    click: { screenModalClick, screenSwitchClick },
    bodyPreview: screenSummary.bodyText.slice(0, 900)
  })
  await clickTarget(client, 'Toggle vision source')
  await wait(150)
  await clickTarget(client, 'Stop active vision capture')
  await wait(250)

  const transcriptTyping = await typeIntoPlaceholder(client, 'Type to Shell, or ask chart about CPU/RAM/network...', 'calculate 2+2')
  await wait(150)
  const transcriptSend = await clickTarget(client, 'Send transcript message')
  await wait(1400)
  const transcriptSummary = await evaluate(client, pageSummaryExpression)
  report.screenshots.dashboard_transcript_prompt = await screenshot(client, 'dashboard_transcript_prompt')
  report.steps.push({
    name: 'dashboard_transcript_prompt',
    ok: transcriptTyping.typed && transcriptSend.clicked && transcriptSummary.bodyText.toLowerCase().includes('calculate 2+2'),
    click: transcriptSend,
    fill: transcriptTyping,
    bodyPreview: transcriptSummary.bodyText.slice(0, 1200)
  })

  const speechProbe = await clickTarget(client, 'Test Shell voice')
  await wait(900)
  const afterSpeech = await evaluate(client, pageSummaryExpression)
  report.steps.push({
    name: 'dashboard_shell_voice_output',
    ok: Boolean(speechProbe.clicked),
    click: speechProbe,
    bodyPreview: afterSpeech.bodyText.slice(0, 900)
  })

  await clickTarget(client, 'Stop Shell voice')
  await wait(500)
  const powerProbe = await clickTarget(client, 'Start Shell voice')
  await wait(900)
  const afterPower = await evaluate(client, pageSummaryExpression)
  report.screenshots.dashboard_after_power = await screenshot(client, 'dashboard_after_power')
  report.steps.push({
    name: 'dashboard_power_button',
    ok: Boolean(powerProbe.clicked),
    click: powerProbe,
    bodyPreview: afterPower.bodyText.slice(0, 900)
  })
  const stopProbe = await clickTarget(client, 'Stop Shell voice')
  await wait(600)
  const afterStop = await evaluate(client, pageSummaryExpression)
  report.screenshots.dashboard_after_stop = await screenshot(client, 'dashboard_after_stop')
  report.steps.push({
    name: 'dashboard_stop_button',
    ok: Boolean(stopProbe.clicked) && afterStop.bodyText.includes('STANDBY'),
    click: stopProbe,
    bodyPreview: afterStop.bodyText.slice(0, 900)
  })

  const errors = client.events
    .filter((event) => event.method === 'Runtime.exceptionThrown' || event.method === 'Log.entryAdded')
    .map((event) => event.params)
  report.console = errors
  report.ok = report.steps.every((step) => step.ok) && !errors.some((entry) => {
    const text = JSON.stringify(entry).toLowerCase()
    return text.includes('uncaught') || text.includes('typeerror') || text.includes('referenceerror')
  })

  const reportPath = path.join(outDir, 'report.json')
  await fs.writeFile(reportPath, JSON.stringify(report, null, 2), 'utf8')
  console.log(JSON.stringify({
    ok: report.ok,
    reportPath,
    screenshots: report.screenshots,
    steps: report.steps.map((step) => ({ name: step.name, ok: step.ok, click: step.click || null })),
    consoleEvents: errors.length
  }, null, 2))
  client.close()
  process.exit(report.ok ? 0 : 1)
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})
