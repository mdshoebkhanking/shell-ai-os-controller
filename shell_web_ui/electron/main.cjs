const { app, BrowserWindow, ipcMain, nativeImage } = require('electron')
const { spawn } = require('node:child_process')
const fs = require('node:fs')
const path = require('node:path')

const WEB_ROOT = path.resolve(__dirname, '..')
const DEV_REPO_ROOT = path.resolve(WEB_ROOT, '..')
const REPO_ROOT = (() => {
  if (process.env.SHELL_ELECTRON_BACKEND_ROOT) return path.resolve(process.env.SHELL_ELECTRON_BACKEND_ROOT)
  if (app.isPackaged && process.platform === 'win32') return path.resolve(process.resourcesPath, '..', '..')
  return DEV_REPO_ROOT
})()
const BRIDGE_SCRIPT = path.join(REPO_ROOT, 'shell_electron_bridge.py')
const PACKAGED_BRIDGE_EXE = path.join(REPO_ROOT, 'ShellAIBackend', 'ShellAIBackend.exe')
const DIST_INDEX = path.join(WEB_ROOT, 'dist', 'index.html')
const LOG_DIR = path.join(REPO_ROOT, '.shell_runtime', 'logs')
const ICON_PATH = path.join(WEB_ROOT, 'dist', 'shell-logo.png')
const FULL_E2E_FIXTURE_DIR = path.join(REPO_ROOT, '.shell_runtime', 'electron_full_e2e_fixture')

let bridgeProcess = null
let bridgeUrl = ''
let mainWindow = null
let eventAbortController = null

function e2eReportPath() {
  if (process.env.SHELL_ELECTRON_TOOL_MATRIX_E2E === '1') {
    return path.join(REPO_ROOT, '.shell_runtime', 'electron_tool_matrix_ui_report.json')
  }
  return process.env.SHELL_ELECTRON_FULL_E2E === '1'
    ? path.join(REPO_ROOT, '.shell_runtime', 'electron_full_ui_e2e_report.json')
    : path.join(REPO_ROOT, '.shell_runtime', 'electron_offline_brain_e2e_report.json')
}

function prepareFullE2EFixture() {
  if (process.env.SHELL_ELECTRON_FULL_E2E !== '1') return
  const crypto = require('node:crypto')
  fs.mkdirSync(FULL_E2E_FIXTURE_DIR, { recursive: true })
  const installerPath = path.join(FULL_E2E_FIXTURE_DIR, 'ShellAI_Setup_9.9.9.exe')
  fs.writeFileSync(installerPath, Buffer.from('Shell AI local updater e2e fixture\n', 'utf8'))
  const sha256 = crypto.createHash('sha256').update(fs.readFileSync(installerPath)).digest('hex')
  const manifest = {
    version: '9.9.9',
    releaseNotes: 'Local Electron E2E update fixture. This file is not a real installer.',
    downloadUrl: `file://${installerPath}`,
    assetName: path.basename(installerPath),
    sha256
  }
  const manifestPath = path.join(FULL_E2E_FIXTURE_DIR, 'manifest.json')
  fs.writeFileSync(manifestPath, JSON.stringify(manifest, null, 2), 'utf8')
  process.env.SHELL_UPDATE_MANIFEST_URL = `file://${manifestPath}`
}

function pythonCommand() {
  if (process.env.SHELL_ELECTRON_PYTHON) return process.env.SHELL_ELECTRON_PYTHON
  if (process.platform === 'win32' && fs.existsSync(PACKAGED_BRIDGE_EXE)) return PACKAGED_BRIDGE_EXE
  const candidates = process.platform === 'win32'
    ? [
        path.join(REPO_ROOT, '.shellai_venv', 'Scripts', 'python.exe'),
        path.join(REPO_ROOT, '.codex_ui_venv', 'Scripts', 'python.exe'),
        'python'
      ]
    : [
        path.join(REPO_ROOT, '.shellai_venv', 'bin', 'python'),
        path.join(REPO_ROOT, '.codex_ui_venv', 'bin', 'python'),
        'python3',
        'python'
      ]
  return candidates.find((candidate) => candidate === 'python' || candidate === 'python3' || fs.existsSync(candidate)) || 'python'
}

function appendLog(name, line) {
  try {
    fs.mkdirSync(LOG_DIR, { recursive: true })
    fs.appendFileSync(path.join(LOG_DIR, name), line)
  } catch {
    // Logging is best-effort.
  }
}

function waitForBridgePort(proc) {
  return new Promise((resolve, reject) => {
    const timeout = setTimeout(() => reject(new Error('Electron bridge did not publish a port.')), 30000)
    const onData = (chunk) => {
      const text = String(chunk)
      appendLog('electron-bridge.log', text)
      const match = text.match(/SHELL_ELECTRON_BRIDGE_PORT=(\d+)/)
      if (!match) return
      clearTimeout(timeout)
      resolve(Number(match[1]))
    }
    proc.stdout.on('data', onData)
    proc.stderr.on('data', (chunk) => appendLog('electron-bridge.log', String(chunk)))
    proc.on('exit', (code) => {
      clearTimeout(timeout)
      reject(new Error(`Electron bridge exited early with code ${code}`))
    })
  })
}

async function startBridge() {
  if (bridgeUrl) return bridgeUrl
  prepareFullE2EFixture()
  const command = pythonCommand()
  const packagedBackend = path.basename(command).toLowerCase() === 'shellaibackend.exe'
  if (!packagedBackend && !fs.existsSync(BRIDGE_SCRIPT)) throw new Error(`Bridge script missing: ${BRIDGE_SCRIPT}`)
  const env = {
    ...process.env,
    PYTHONUTF8: '1',
    PYTHONIOENCODING: 'utf-8',
    SHELL_IMAGE_LOCAL_FALLBACK: process.env.SHELL_IMAGE_LOCAL_FALLBACK || '1',
    SHELL_OFFLINE_LLM_ASYNC_UI: process.env.SHELL_OFFLINE_LLM_ASYNC_UI || '1',
    SHELL_WINDOWS_PERFORMANCE_MODE: process.env.SHELL_WINDOWS_PERFORMANCE_MODE || 'balanced',
    SHELL_APP_ROOT: REPO_ROOT,
    SHELL_INSTALL_ROOT: REPO_ROOT,
    SHELL_RUNTIME_DIR: path.join(REPO_ROOT, '.shell_runtime'),
    SHELL_ELECTRON_HOST: '1'
  }
  bridgeProcess = spawn(command, packagedBackend ? ['--port', '0'] : [BRIDGE_SCRIPT, '--port', '0'], {
    cwd: REPO_ROOT,
    env,
    windowsHide: true
  })
  const port = await waitForBridgePort(bridgeProcess)
  bridgeUrl = `http://127.0.0.1:${port}`
  subscribeBridgeEvents()
  return bridgeUrl
}

async function subscribeBridgeEvents() {
  if (!bridgeUrl || !mainWindow) return
  eventAbortController?.abort()
  eventAbortController = new AbortController()
  try {
    const response = await fetch(`${bridgeUrl}/events`, { signal: eventAbortController.signal })
    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    while (true) {
      const { value, done } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const packets = buffer.split('\n\n')
      buffer = packets.pop() || ''
      for (const packet of packets) {
        const line = packet.split('\n').find((item) => item.startsWith('data: '))
        if (!line) continue
        try {
          mainWindow.webContents.send('shell-bridge-event', JSON.parse(line.slice(6)))
        } catch {
          // Ignore malformed bridge events.
        }
      }
    }
  } catch (error) {
    if (error?.name !== 'AbortError') appendLog('electron-bridge.log', `event stream failed: ${error?.message || error}\n`)
  }
}

async function createWindow() {
  const url = await startBridge()
  const icon = fs.existsSync(ICON_PATH) ? nativeImage.createFromPath(ICON_PATH) : undefined
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 760,
    minWidth: 1040,
    minHeight: 680,
    backgroundColor: '#05070d',
    icon,
    show: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
      webSecurity: true
    }
  })
  subscribeBridgeEvents()
  mainWindow.webContents.on('console-message', (_event, level, message, line, sourceId) => {
    appendLog('electron-renderer.log', `[console:${level}] ${message} (${sourceId}:${line})\n`)
  })
  mainWindow.webContents.on('did-fail-load', (_event, errorCode, errorDescription, validatedURL) => {
    appendLog('electron-renderer.log', `[did-fail-load] ${errorCode} ${errorDescription} ${validatedURL}\n`)
  })
  mainWindow.webContents.on('render-process-gone', (_event, details) => {
    appendLog('electron-renderer.log', `[render-process-gone] ${JSON.stringify(details)}\n`)
  })
  mainWindow.once('ready-to-show', () => mainWindow.show())
  mainWindow.webContents.once('did-finish-load', async () => {
    mainWindow.webContents.send('shell-bridge-ready', { ok: true, url })
    try {
      const probe = await mainWindow.webContents.executeJavaScript(`({
        href: location.href,
        title: document.title,
        rootChildren: document.getElementById('root')?.childElementCount || 0,
        bodyText: document.body?.innerText?.slice(0, 240) || '',
        scripts: Array.from(document.scripts).map((script) => script.src || 'inline').slice(0, 10)
      })`)
      appendLog('electron-renderer.log', `[dom-probe] ${JSON.stringify(probe)}\n`)
    } catch (error) {
      appendLog('electron-renderer.log', `[dom-probe-error] ${error?.stack || error}\n`)
    }
    if (process.env.SHELL_ELECTRON_TOOL_MATRIX_E2E === '1') {
      try {
        const matrixScript = path.join(REPO_ROOT, 'tools', 'electron_tool_matrix_renderer_probe.js')
        const source = fs.readFileSync(matrixScript, 'utf8')
        const report = await mainWindow.webContents.executeJavaScript(`
          (async () => {
            ${source}
          })()
        `)
        fs.mkdirSync(path.dirname(e2eReportPath()), { recursive: true })
        fs.writeFileSync(e2eReportPath(), JSON.stringify(report, null, 2), 'utf8')
        appendLog('electron-renderer.log', `[tool-matrix-report] ${e2eReportPath()}\n`)
      } catch (error) {
        const report = { ok: false, error: String(error?.stack || error), ts: new Date().toISOString() }
        fs.mkdirSync(path.dirname(e2eReportPath()), { recursive: true })
        fs.writeFileSync(e2eReportPath(), JSON.stringify(report, null, 2), 'utf8')
        appendLog('electron-renderer.log', `[tool-matrix-error] ${error?.stack || error}\n`)
      } finally {
        if (process.env.SHELL_ELECTRON_E2E_QUIT === '1') setTimeout(() => app.quit(), 750)
      }
      return
    }
    if (process.env.SHELL_ELECTRON_E2E === '1') {
      try {
        const fullE2E = process.env.SHELL_ELECTRON_FULL_E2E === '1'
        const report = await mainWindow.webContents.executeJavaScript(`
          (async () => {
            const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms))
            const invoke = (...args) => window.electron.ipcRenderer.invoke(...args)
            const events = []
            const fullE2E = ${fullE2E ? 'true' : 'false'}
            const eventNames = ['chat-updated', 'speech-status', 'voice-amplitude', 'voice-status', 'offline-llm-download-event', 'updater-event']
            const waiters = new Map()
            const waitForEvent = (name, predicate, timeoutMs = 30000) => new Promise((resolve) => {
              const deadline = Date.now() + timeoutMs
              const key = name + ':' + Math.random().toString(36).slice(2)
              const timer = setInterval(() => {
                if (Date.now() > deadline) {
                  clearInterval(timer)
                  waiters.delete(key)
                  resolve(null)
                }
              }, 100)
              waiters.set(key, { name, predicate, resolve: (payload) => {
                clearInterval(timer)
                waiters.delete(key)
                resolve(payload)
              }})
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
            const textOf = (node) => String(node?.innerText || node?.textContent || '').replace(/\\s+/g, ' ').trim()
            const buttons = () => Array.from(document.querySelectorAll('button'))
            const findButton = (match) => buttons().find((button) => {
              const label = String(button.getAttribute('aria-label') || '')
              const text = textOf(button)
              return typeof match === 'string'
                ? label === match || text === match
                : match(label, text, button)
            })
            const clickButton = async (match, label) => {
              const button = findButton(match)
              const record = {
                label,
                found: Boolean(button),
                disabled: Boolean(button?.disabled),
                before: document.body?.innerText?.slice(0, 180) || ''
              }
              if (!button || button.disabled) return record
              const started = performance.now()
              button.click()
              await wait(250)
              record.durationMs = Math.round((performance.now() - started) * 10) / 10
              record.rootChildren = document.getElementById('root')?.childElementCount || 0
              record.after = document.body?.innerText?.slice(0, 240) || ''
              record.ok = record.rootChildren > 0
              return record
            }
            const latestEventPayload = (name, predicate) => {
              const matches = events.filter((record) => {
                if (record.name !== name) return false
                if (!predicate) return true
                try {
                  return predicate(record.payload)
                } catch {
                  return false
                }
              })
              return matches.length ? matches[matches.length - 1].payload : null
            }
            const measureResponsiveness = async (durationMs = 1200) => {
              const start = performance.now()
              let frames = 0
              let maxGap = 0
              let last = start
              return new Promise((resolve) => {
                const tick = (now) => {
                  frames += 1
                  maxGap = Math.max(maxGap, now - last)
                  last = now
                  if (now - start >= durationMs) {
                    resolve({
                      durationMs: Math.round((now - start) * 10) / 10,
                      frames,
                      fps: Math.round((frames / Math.max(0.001, (now - start) / 1000)) * 10) / 10,
                      maxFrameGapMs: Math.round(maxGap * 10) / 10
                    })
                    return
                  }
                  requestAnimationFrame(tick)
                }
                requestAnimationFrame(tick)
              })
            }
            const nextPaint = () =>
              new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)))
            const measureFastTabSwitch = async (tabId) => {
              const button = findButton('Open ' + tabId + ' view')
              const record = {
                tabId,
                found: Boolean(button),
                disabled: Boolean(button?.disabled),
                ok: false,
                durationMs: null,
                frames: 0,
                sawSkeleton: false,
                active: false
              }
              if (!button || button.disabled) return record
              const started = performance.now()
              button.click()
              for (let index = 0; index < 10; index += 1) {
                await nextPaint()
                record.frames += 2
                const body = document.body?.innerText || ''
                record.sawSkeleton = record.sawSkeleton || body.includes('INITIALIZING MODULE')
                record.active = button.classList.contains('shell-tab-active')
                if (record.active && !body.includes('INITIALIZING MODULE')) break
              }
              record.durationMs = Math.round((performance.now() - started) * 10) / 10
              record.ok = record.active && !record.sawSkeleton
              record.rootChildren = document.getElementById('root')?.childElementCount || 0
              record.after = document.body?.innerText?.slice(0, 220) || ''
              return record
            }
            const pageChecks = []
            const settingsChecks = []
            const buttonChecks = []
            const fastTabChecks = []
            await wait(800)
            if (fullE2E) {
              for (const view of ['DASHBOARD', 'Apps', 'NOTES', 'GALLERY', 'CONTROL', 'SETTINGS']) {
                pageChecks.push(await clickButton('Open ' + view + ' view', 'tab:' + view))
              }
              buttonChecks.push(await clickButton('Open more Shell views', 'more-tabs'))
              for (const view of ['Macros', 'PHONE']) {
                pageChecks.push(await clickButton('Open ' + view + ' view', 'tab:' + view))
              }
              pageChecks.push(await clickButton('Open SETTINGS view', 'tab:SETTINGS:return'))
              settingsChecks.push(await clickButton('Open settings general tab', 'settings:general'))
              settingsChecks.push(await clickButton((label, text) => text === 'REFRESH', 'settings:first-refresh'))
              const offlineBrainRefresh = buttons().filter((button) => textOf(button) === 'REFRESH')[1]
              if (offlineBrainRefresh) {
                offlineBrainRefresh.click()
                await wait(500)
                settingsChecks.push({ label: 'settings:offline-brain-refresh', found: true, rootChildren: document.getElementById('root')?.childElementCount || 0, ok: true })
              } else {
                settingsChecks.push({ label: 'settings:offline-brain-refresh', found: false, ok: false })
              }
              settingsChecks.push(await clickButton('Open settings system tab', 'settings:system'))
              const updateButton = findButton((_label, text) => text.includes('CHECK FOR UPDATES'))
              const updateWait = waitForEvent('updater-event', (payload) => payload && ['available', 'not-available', 'error'].includes(String(payload.status || '')), 15000)
              const updateClickStarted = performance.now()
              if (updateButton) updateButton.click()
              const updateResponsiveness = await measureResponsiveness(1500)
              const updateEvent = latestEventPayload('updater-event', (payload) => payload && ['available', 'not-available', 'error'].includes(String(payload.status || ''))) || await updateWait
              let updateDownloadResult = null
              let updateDownloadResponsiveness = null
              if (updateEvent?.status === 'available') {
                const downloadButton = findButton((_label, text) => text.includes('DOWNLOAD UPDATE'))
                const downloadWait = waitForEvent('updater-event', (payload) => payload && ['downloaded', 'error'].includes(String(payload.status || '')), 15000)
                if (downloadButton) downloadButton.click()
                updateDownloadResponsiveness = await measureResponsiveness(1500)
                updateDownloadResult = latestEventPayload('updater-event', (payload) => payload && ['downloaded', 'error'].includes(String(payload.status || ''))) || await downloadWait
              }
              settingsChecks.push({
                label: 'settings:update-check',
                found: Boolean(updateButton),
                clickReturnMs: Math.round((performance.now() - updateClickStarted) * 10) / 10,
                responsiveness: updateResponsiveness,
                event: updateEvent,
                downloadResponsiveness: updateDownloadResponsiveness,
                downloadEvent: updateDownloadResult,
                ok: Boolean(updateButton) && Boolean(updateEvent)
              })
              pageChecks.push(await clickButton('Open DASHBOARD view', 'tab:DASHBOARD:return'))
              buttonChecks.push(await clickButton('Toggle vision source', 'dock:vision-modal'))
              buttonChecks.push(await clickButton('Close vision source selector', 'dock:vision-modal-close'))
              buttonChecks.push(await clickButton((label) => label === 'Mute microphone' || label === 'Unmute microphone', 'dock:mic-toggle'))
              buttonChecks.push(await clickButton('Test Shell voice', 'dock:test-voice-button'))
              buttonChecks.push(await clickButton('Clear transcript', 'dashboard:clear-transcript'))
            }
            const initialStatus = await invoke('offline-llm-status')
            const catalog = await invoke('offline-llm-catalog')
            let selectedResult = null
            if (initialStatus?.selectedModelId !== 'qwen2.5-0.5b-q4' || initialStatus?.available !== true) {
              selectedResult = await invoke('offline-llm-download', { modelId: 'qwen2.5-0.5b-q4' })
            }
            const selectedStatus = await invoke('offline-llm-status')
            const textResult = await invoke(
              'chat-message',
              'Reply one short line: Electron E2E local brain test. What is 9 plus 6?',
              { source: 'text', entry: 'chart' }
            )
            const textFinal = textResult?.pending
              ? await waitForEvent('chat-updated', (payload) => payload && payload.pending === false && payload.source === 'text', 45000)
              : null
            const voiceResult = await invoke(
              'chat-message',
              'Reply in Hinglish one short line: Electron voice-source local test successful hai?',
              { source: 'voice', entry: 'chart' }
            )
            const voiceFinal = voiceResult?.pending
              ? await waitForEvent('chat-updated', (payload) => payload && payload.pending === false && payload.source === 'voice', 45000)
              : null
            const speechWait = waitForEvent('speech-status', (payload) => payload && ['queued', 'speaking', 'error', 'fallback'].includes(String(payload.state || '')), 10000)
            const speechSpeakingWait = waitForEvent('speech-status', (payload) => payload && ['speaking', 'error', 'fallback'].includes(String(payload.state || '')), 12000)
            const ttsResult = await invoke('speak-text', 'Command center ready.')
            const speechEvent = await speechWait
            const speechSpeakingEvent = await speechSpeakingWait
            const readOrbReaction = () => {
              const stage = document.querySelector('.shell-orb-stage')
              const style = stage ? getComputedStyle(stage) : null
              return {
                found: Boolean(stage),
                speaking: Boolean(stage?.classList.contains('shell-orb-stage-speaking')),
                level: Number(style?.getPropertyValue('--shell-orb-level') || 0),
                scale: Number(style?.getPropertyValue('--shell-orb-scale') || 0),
                className: String(stage?.className || '')
              }
            }
            const waitForOrbReaction = async (timeoutMs = 2500) => {
              const deadline = Date.now() + timeoutMs
              let latest = readOrbReaction()
              while (Date.now() < deadline) {
                latest = readOrbReaction()
                if (latest.speaking || latest.level > 0.04) return { ...latest, ok: true }
                await wait(80)
              }
              return { ...latest, ok: false }
            }
            const orbReaction = await waitForOrbReaction()
            let onlineVoiceResult = null
            let onlineVoiceEvent = null
            let voiceStartResult = null
            let voiceStartEvent = null
            let voiceStopResult = null
            let onlineBrainResult = null
            let onlineBrainFinal = null
            let fullResponsiveness = null
            if (fullE2E) {
              onlineVoiceResult = await invoke('speak-text', 'Electron online voice readiness test.')
              onlineVoiceEvent = await waitForEvent('speech-status', (payload) => payload && ['speaking', 'queued', 'fallback', 'error'].includes(String(payload.state || '')), 10000)
              voiceStartResult = await invoke('start-voice')
              voiceStartEvent = await waitForEvent('voice-status', (payload) => payload && ['starting', 'listening', 'error', 'stopped'].includes(String(payload.state || '')), 10000)
              await wait(600)
              voiceStopResult = await invoke('stop-voice')
              onlineBrainResult = await invoke(
                'chat-message',
                'Online brain readiness check: reply one short line with provider or fallback status.',
                { source: 'text', entry: 'chart', providerMode: 'auto' }
              )
              onlineBrainFinal = onlineBrainResult?.pending
                ? await waitForEvent('chat-updated', (payload) => payload && payload.pending === false && payload.source === 'text', 45000)
                : null
              fullResponsiveness = await measureResponsiveness(1500)
              for (const tabId of ['Apps', 'NOTES', 'GALLERY', 'CONTROL', 'SETTINGS', 'DASHBOARD']) {
                fastTabChecks.push(await measureFastTabSwitch(tabId))
              }
            }
            await wait(1000)
            return {
              ok: true,
              href: location.href,
              rootChildren: document.getElementById('root')?.childElementCount || 0,
              bodyText: document.body?.innerText?.slice(0, 800) || '',
              initialStatus,
              catalogSummary: {
                selectedModelId: catalog?.selectedModelId,
                available: catalog?.available,
                options: Array.isArray(catalog?.models) ? catalog.models.length : Array.isArray(catalog?.options) ? catalog.options.length : null
              },
              selectedResult,
              selectedStatus,
              textResult,
              textFinal,
              voiceResult,
              voiceFinal,
              ttsResult,
              speechEvent,
              speechSpeakingEvent,
              orbReaction,
              fullE2E,
              pageChecks,
              settingsChecks,
              buttonChecks,
              fastTabChecks,
              onlineVoiceResult,
              onlineVoiceEvent,
              voiceStartResult,
              voiceStartEvent,
              voiceStopResult,
              onlineBrainResult,
              onlineBrainFinal,
              fullResponsiveness,
              events: events.slice(-40)
            }
          })()
        `)
        fs.mkdirSync(path.dirname(e2eReportPath()), { recursive: true })
        fs.writeFileSync(e2eReportPath(), JSON.stringify(report, null, 2), 'utf8')
        appendLog('electron-renderer.log', `[e2e-report] ${e2eReportPath()}\n`)
      } catch (error) {
        const report = { ok: false, error: String(error?.stack || error), ts: new Date().toISOString() }
        fs.mkdirSync(path.dirname(e2eReportPath()), { recursive: true })
        fs.writeFileSync(e2eReportPath(), JSON.stringify(report, null, 2), 'utf8')
        appendLog('electron-renderer.log', `[e2e-error] ${error?.stack || error}\n`)
      } finally {
        if (process.env.SHELL_ELECTRON_E2E_QUIT === '1') setTimeout(() => app.quit(), 750)
      }
    }
  })
  const devUrl = process.env.SHELL_ELECTRON_DEV_URL || ''
  if (devUrl) {
    await mainWindow.loadURL(devUrl)
  } else {
    await mainWindow.loadFile(DIST_INDEX, {
      query: {
        shell_host: 'electron',
        shell_perf: process.platform === 'win32' ? 'windows' : 'desktop'
      }
    })
  }
}

ipcMain.handle('shell-bridge-call', async (_event, channel, args) => {
  const url = await startBridge()
  const response = await fetch(`${url}/call`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ channel, args: Array.isArray(args) ? args : [] })
  })
  const payload = await response.json()
  if (payload && Object.prototype.hasOwnProperty.call(payload, 'data')) return payload.data
  return payload
})

app.whenReady().then(createWindow)
app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow().catch((error) => appendLog('electron-main.log', `${error.stack || error}\n`))
})
app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})
app.on('before-quit', () => {
  eventAbortController?.abort()
  if (bridgeProcess && !bridgeProcess.killed) bridgeProcess.kill()
})
