const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms))
const originalInvoke = window.electron.ipcRenderer.invoke.bind(window.electron.ipcRenderer)
const invoke = (...args) => originalInvoke(...args)
try {
  window.electron.ipcRenderer.invoke = async (channel, ...args) => {
    if (channel === 'speak-text') {
      return { success: true, mutedByProbe: true, source: 'tool-matrix-probe' }
    }
    return originalInvoke(channel, ...args)
  }
} catch {}

const events = []
const waiters = new Map()
const eventNames = ['chat-updated', 'activity-updated', 'speech-status', 'voice-status']
const waitForEvent = (name, predicate, timeoutMs = 12000) => new Promise((resolve) => {
  const key = `${name}:${Math.random().toString(36).slice(2)}`
  const timer = setTimeout(() => {
    waiters.delete(key)
    resolve(null)
  }, timeoutMs)
  waiters.set(key, {
    name,
    predicate,
    resolve: (payload) => {
      clearTimeout(timer)
      waiters.delete(key)
      resolve(payload)
    }
  })
})
for (const name of eventNames) {
  window.electron.ipcRenderer.on(name, (_event, payload) => {
    const record = { name, payload, ts: Date.now() }
    events.push(record)
    for (const [key, waiter] of Array.from(waiters.entries())) {
      if (waiter.name !== name) continue
      try {
        if (!waiter.predicate || waiter.predicate(payload)) waiter.resolve(payload)
      } catch {}
    }
  })
}

const textOf = (node) => String(node?.innerText || node?.textContent || '').replace(/\s+/g, ' ').trim()
const buttons = () => Array.from(document.querySelectorAll('button'))
const findButton = (match) => buttons().find((button) => {
  const label = String(button.getAttribute('aria-label') || '')
  const text = textOf(button)
  return typeof match === 'string' ? label === match || text === match : match(label, text, button)
})
const clickButton = async (match) => {
  const button = findButton(match)
  if (!button || button.disabled) return false
  button.click()
  await wait(250)
  return true
}
const inputValueSetter = (node, value) => {
  const descriptor = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')
  if (descriptor?.set) descriptor.set.call(node, value)
  else node.value = value
  node.dispatchEvent(new Event('input', { bubbles: true }))
}
const sendViaChatUi = async (command, toolId, timeoutMs = 15000) => {
  const input = document.querySelector('[aria-label="Shell command input"]')
  const send = document.querySelector('[aria-label="Send transcript message"]')
  const row = {
    command,
    inputFound: Boolean(input),
    sendFound: Boolean(send),
    sendDisabled: Boolean(send?.disabled),
    status: 'not-started',
    ok: false
  }
  if (!input || !send || send.disabled) {
    row.status = 'ui-missing'
    return row
  }
  const started = performance.now()
  const eventWait = waitForEvent(
    'chat-updated',
    (payload) => String(payload?.route?.tool || '') === toolId || String(payload?.reply || '').includes(toolId),
    timeoutMs
  )
  input.focus()
  inputValueSetter(input, command)
  send.click()
  const event = await eventWait
  row.elapsedMs = Math.round((performance.now() - started) * 10) / 10
  row.event = event ? {
    success: event.success,
    source: event.source,
    voice: event.voice,
    pending: event.pending,
    routeTool: event.route?.tool,
    replyTail: String(event.reply || '').slice(-360)
  } : null
  row.status = event ? 'event' : 'timeout'
  row.ok = Boolean(event && event.success !== false && String(event.route?.tool || '') === toolId)
  return row
}
const sendViaVoiceSource = async (command, toolId, timeoutMs = 15000) => {
  const started = performance.now()
  const eventWait = waitForEvent(
    'chat-updated',
    (payload) => (
      String(payload?.source || '') === 'voice'
      && (String(payload?.route?.tool || '') === toolId || String(payload?.reply || '').includes(toolId))
    ),
    timeoutMs
  )
  const result = await invoke('chat-message', command, { source: 'voice', entry: 'chart' })
  const event = result?.pending ? await eventWait : (await Promise.race([eventWait, wait(80).then(() => null)]))
  const payload = event || result
  return {
    command,
    elapsedMs: Math.round((performance.now() - started) * 10) / 10,
    result: {
      success: result?.success,
      source: result?.source,
      pending: result?.pending,
      routeTool: result?.route?.tool,
      replyTail: String(result?.reply || '').slice(-260)
    },
    event: event ? {
      success: event.success,
      source: event.source,
      voice: event.voice,
      pending: event.pending,
      routeTool: event.route?.tool,
      replyTail: String(event.reply || '').slice(-260)
    } : null,
    ok: Boolean(payload && payload.success !== false && String(payload.route?.tool || payload.routeTool || '') === toolId && (payload.source === 'voice' || payload.voice === true))
  }
}

const safetySkipRe = /(delete|remove|cleanup|clean_|clear|reset|wipe|format|kill|shutdown|restart|sleep|lock_pc|system_power|terminal|powershell|run_command|execute|python|workflow|hotpatch|self_heal|evolution|autopilot|daemon|monitor|install|backup|restore|write|save|create_|add_|remember|learn|send_email|send_social|send_telegram|whatsapp|instagram|post|upload|desktop_click|desktop_type|desktop_shortcut|mouse|keyboard|brightness|volume|download_file|youtube_audio_download)/i
const environmentSkipRe = /(network_health|ping_host|dns_lookup|check_port|speedtest|stock_|crypto_|latest_news|traceroute|trace_route|god_mode|hyper_cortex|omni_brain|check_disk_health|disk_health|event_log|resource_hogs|system_diagnostic|scan_system_health|browser|youtube|download|scrape|gmail_web|company_email_web|open_url|web_|port_scan|net_scan|agent_browser)/i

const sampleValue = (param, item) => {
  const name = String(param?.name || '').toLowerCase()
  const ann = String(param?.annotation || '').toLowerCase()
  const toolId = String(item?.id || '').toLowerCase()
  if (['dry_run', 'preview', 'simulate'].includes(name)) return true
  if (ann.includes('bool')) return false
  if (ann.includes('int') && !ann.includes('bool')) {
    if (name === 'port') return 80
    if (['x', 'y'].includes(name)) return 10
    if (['width', 'height'].includes(name)) return 120
    if (['limit', 'number', 'num_dice', 'sides', 'length', 'count', 'end_page', 'start_page', 'top_n', 'min_size_mb'].includes(name)) return 1
    return 1
  }
  if (ann.includes('float')) return 1.0
  if (ann.includes('dict')) return { probe: true }
  if (ann.includes('list')) return ['Shell UI probe']
  if (['text', 'message', 'content', 'body', 'prompt', 'info', 'fact', 'user_input'].includes(name)) return 'Shell UI probe sample'
  if (['task', 'query', 'goal', 'complex_task', 'mission_objective'].includes(name)) return 'UI smoke test only. Return one short safe sentence. Do not modify files or run commands.'
  if (name === 'subject') return 'Shell UI probe'
  if (['recipient', 'email', 'to'].includes(name)) return 'nobody@example.com'
  if (name === 'url') return 'https://example.com'
  if (['host', 'domain'].includes(name)) return 'example.com'
  if (name === 'platform') return 'telegram'
  if (name === 'password') return 'ProbePass123!'
  if (name === 'algorithm') return 'sha256'
  if (name === 'encoding') return 'base64'
  if (['target_lang', 'language'].includes(name)) return 'Hindi'
  if (name === 'from_unit') return 'meter'
  if (name === 'to_unit') return 'centimeter'
  if (name === 'from_base') return 10
  if (name === 'to_base') return 2
  if (name === 'expression') return '2 + 3 * 4'
  if (name === 'numbers') return '1, 2, 3, 4'
  if (name === 'pattern') return '\\w+'
  if (name === 'replacement') return 'probe'
  if (name === 'test_string') return 'Shell UI probe'
  if (['json_string', 'json_text'].includes(name)) return '{"shell": true}'
  if (name === 'case_type') return 'upper'
  if (name === 'player_choice') return 'rock'
  if (name === 'action') return toolId.includes('task') ? 'list' : 'status'
  if (['app_title', 'app_name', 'window_title'].includes(name)) return 'Calculator'
  if (name === 'filename') return 'ui_probe.txt'
  if (['save_path', 'output', 'output_path'].includes(name)) return 'ui_probe_output.txt'
  if (['output_dir', 'save_dir', 'directory', 'directory_path', 'folder_path'].includes(name)) return '.shell_runtime/ui_probe'
  if (['filepath', 'file_path', 'input_path', 'source_path', 'path'].includes(name)) return 'README.md'
  if (['file1', 'file2'].includes(name)) return 'README.md'
  if (['input_paths', 'pdf_paths', 'urls'].includes(name)) return 'README.md'
  if (['zip_path', 'tar_path'].includes(name)) return '.shell_runtime/ui_probe/archive.zip'
  if (['source', 'source_text'].includes(name)) return 'Shell UI probe'
  if (['workflow_name', 'task_name', 'tag', 'project_name', 'persona_name', 'voice_name'].includes(name)) return 'probe'
  if (name === 'value') return 42
  if (['cc', 'bcc', 'attachments', 'html_body'].includes(name)) return ''
  return 'Shell UI probe'
}
const sampleArgs = (item) => {
  const args = {}
  const safeOptional = new Set([
    'dry_run', 'preview', 'simulate', 'top_n', 'limit', 'count', 'min_size_mb', 'start_page', 'end_page'
  ])
  for (const param of item?.params || []) {
    const name = String(param?.name || '')
    if (param?.required || safeOptional.has(name.toLowerCase())) args[name] = sampleValue(param, item)
  }
  return args
}
const shouldSkipExecution = (item) => {
  const toolId = String(item?.id || '')
  const category = String(item?.category || '')
  const meta = item?.metadata || {}
  const safety = String(meta?.safety_level || '')
  const blob = ['id', 'name', 'title', 'description', 'category', 'risk']
    .map((key) => String(item?.[key] || ''))
    .join(' ')
  if (category && ['ai', 'files', 'media', 'desktop', 'system'].includes(category)) return [true, `${category} category readiness-only in full catalog sweep`]
  if (['dangerous', 'experimental', 'guarded'].includes(safety)) return [true, `safety_level=${safety}`]
  if (/^(shell_mcp|mcp_|shell_memory)/i.test(toolId)) return [true, 'stateful integration readiness-only in full catalog sweep']
  if (safetySkipRe.test(blob)) return [true, 'mutation/destructive/external-send keyword']
  if (environmentSkipRe.test(blob)) return [true, 'environment/network-heavy live execution skipped']
  if (/(speech|speak|voice|audio|music|play_|vision|screenshot|screen|click|window)/i.test(toolId)) return [true, 'audio/speech/desktop readiness-only in full catalog sweep']
  return [false, '']
}
const commandFor = (item, args) => {
  const prefix = item?.kind === 'agent' ? '/agent' : '/tool'
  return `${prefix} ${item.id} ${JSON.stringify(args)}`
}

await wait(900)
await clickButton('Open DASHBOARD view')
await wait(300)
const capabilityPayload = await invoke('get-capabilities')
const catalog = Array.isArray(capabilityPayload?.catalog)
  ? capabilityPayload.catalog
  : Array.isArray(capabilityPayload?.tools)
    ? capabilityPayload.tools
    : []
const report = {
  ok: true,
  href: location.href,
  rootChildren: document.getElementById('root')?.childElementCount || 0,
  ui: {
    dashboardClicked: true,
    chatInputFound: Boolean(document.querySelector('[aria-label="Shell command input"]')),
    sendButtonFound: Boolean(document.querySelector('[aria-label="Send transcript message"]')),
    mutedVoiceReplies: true
  },
  summary: {
    total: catalog.length,
    chatExecuted: 0,
    chatPassed: 0,
    chatFailed: 0,
    voiceExecuted: 0,
    voicePassed: 0,
    voiceFailed: 0,
    skippedBySafety: 0,
    expectedNotReady: 0,
    agentExecuted: 0
  },
  rows: [],
  startedAt: new Date().toISOString()
}

for (const [index, item] of catalog.entries()) {
  const readiness = item?.readiness || {}
  const meta = item?.metadata || {}
  const [skipBySafety, safetyReason] = item?.kind === 'agent' ? [false, ''] : shouldSkipExecution(item)
  const readinessOk = readiness?.ok !== false
  const args = sampleArgs(item)
  const command = commandFor(item, args)
  const row = {
    index: index + 1,
    id: item?.id,
    kind: item?.kind,
    category: item?.category,
    readinessState: readiness?.state,
    readinessOk,
    safetyLevel: meta?.safety_level,
    command,
    args,
    skipped: false,
    skipReason: ''
  }

  if (!readinessOk) {
    row.skipped = true
    row.skipReason = `readiness-only: ${readiness?.state || 'not ready'}`
    report.summary.expectedNotReady += 1
  } else if (skipBySafety) {
    row.skipped = true
    row.skipReason = safetyReason
    report.summary.skippedBySafety += 1
  } else {
    if (item?.kind === 'agent') report.summary.agentExecuted += 1
    row.chat = await sendViaChatUi(command, item.id, item?.kind === 'agent' ? 25000 : 15000)
    report.summary.chatExecuted += 1
    if (row.chat.ok) report.summary.chatPassed += 1
    else {
      report.summary.chatFailed += 1
      report.ok = false
    }
    row.voice = await sendViaVoiceSource(command, item.id, item?.kind === 'agent' ? 25000 : 15000)
    report.summary.voiceExecuted += 1
    if (row.voice.ok) report.summary.voicePassed += 1
    else {
      report.summary.voiceFailed += 1
      report.ok = false
    }
  }
  report.rows.push(row)
}

report.finishedAt = new Date().toISOString()
report.eventTail = events.slice(-30)
return report
