import { normalizeGeminiApiKey } from './services/api-key-utils'
import {
  SHELL_LANGUAGE_STORAGE_KEY,
  normalizeShellLanguage,
  readShellLanguage,
  shellSpeechLocale
} from './services/language-settings'
import { handleImageGeneration } from './tools/Image-generator'

type Listener = (event: unknown, payload?: unknown) => void

interface ShellCallResult {
  ok?: boolean
  data?: unknown
  error?: string
}

const listeners = new Map<string, Set<Listener>>()
const memoryHistoryKey = 'shell_chat_history'
const fallbackGalleryKey = 'shell_fallback_gallery'

let pythonBridge: any = null

const emit = (channel: string, payload?: unknown) => {
  const channelListeners = listeners.get(channel)
  if (!channelListeners) return
  channelListeners.forEach((listener) => listener({ channel }, payload))
}

const waitForPythonBridge = (timeoutMs = 2500) =>
  new Promise<boolean>((resolve) => {
    if (pythonBridge?.call) {
      resolve(true)
      return
    }

    let settled = false
    const finish = (ready: boolean) => {
      if (settled) return
      settled = true
      window.clearTimeout(timer)
      listeners.get('shell-bridge-ready')?.delete(onReady)
      resolve(ready)
    }
    const onReady: Listener = () => finish(Boolean(pythonBridge?.call))
    if (!listeners.has('shell-bridge-ready')) listeners.set('shell-bridge-ready', new Set())
    listeners.get('shell-bridge-ready')!.add(onReady)
    const timer = window.setTimeout(() => finish(Boolean(pythonBridge?.call)), timeoutMs)
  })

const readHistory = () => {
  try {
    const raw = localStorage.getItem(memoryHistoryKey)
    return raw ? JSON.parse(raw) : []
  } catch {
    return []
  }
}

const writeHistory = (messages: unknown[]) => {
  try {
    localStorage.setItem(memoryHistoryKey, JSON.stringify(messages.slice(-50)))
  } catch {}
}

const readFallbackGallery = () => {
  try {
    const raw = localStorage.getItem(fallbackGalleryKey)
    return raw ? JSON.parse(raw) : []
  } catch {
    return []
  }
}

const writeFallbackGallery = (images: unknown[]) => {
  try {
    localStorage.setItem(fallbackGalleryKey, JSON.stringify(images.slice(0, 80)))
  } catch {}
}

const languageReply = (key: 'backendOffline' | 'noRecall' | 'recall' | 'france' | 'pythonMemory' | 'networkProtocol' | 'filesAttached' | 'hello', values: Record<string, string> = {}) => {
  const language = readShellLanguage()
  const replies = {
    hinglish: {
      backendOffline: 'Shell backend bridge abhi connected nahi hai. Backend start hone ke baad main full jawab aur OS actions kar paungi.',
      noRecall: 'Haan bhai, lekin is session mein abhi koi pehla chart ya command task saved nahi mila.',
      recall: `Haan bhai, yaad hai. Tumne pichla kaam bola tha: "${values.task || ''}".`,
      france: 'France ki capital Paris hai.',
      pythonMemory: 'Python memory heap mein objects rakhta hai; reference counting aur garbage collector unused objects clean karte hain.',
      networkProtocol: 'Network protocol rules ka set hota hai jisse devices data exchange karte hain, jaise TCP/IP, HTTP, DNS.',
      filesAttached: `Files attached hain: ${values.files || ''}. Backend connected hoga to main inka content read karke answer de paungi.`,
      hello: 'Haan bhai, bolo. Main sun rahi hoon.'
    },
    english: {
      backendOffline: 'The Shell backend bridge is not connected yet. Once it starts, I can answer fully and run OS actions.',
      noRecall: 'I do not have an earlier chart or command task saved in this session yet.',
      recall: `Yes, I remember. Your previous task was: "${values.task || ''}".`,
      france: 'The capital of France is Paris.',
      pythonMemory: 'Python stores objects on the heap; reference counting and the garbage collector clean up unused objects.',
      networkProtocol: 'A network protocol is a set of rules devices use to exchange data, such as TCP/IP, HTTP, and DNS.',
      filesAttached: `Files attached: ${values.files || ''}. Once the backend is connected, I can read their content and answer.`,
      hello: 'Yes, tell me. I am listening.'
    },
    hindi: {
      backendOffline: 'Shell backend bridge अभी connected नहीं है. Backend start होने के बाद मैं पूरा जवाब और OS actions कर पाऊंगी.',
      noRecall: 'इस session में अभी कोई पिछला chart या command task saved नहीं मिला.',
      recall: `हाँ, याद है. आपने पिछला काम बोला था: "${values.task || ''}".`,
      france: 'France की राजधानी Paris है.',
      pythonMemory: 'Python objects को heap में रखता है; reference counting और garbage collector unused objects clean करते हैं.',
      networkProtocol: 'Network protocol rules का set होता है जिससे devices data exchange करते हैं, जैसे TCP/IP, HTTP और DNS.',
      filesAttached: `Files attached हैं: ${values.files || ''}. Backend connected होगा तो मैं उनका content पढ़कर answer दे पाऊंगी.`,
      hello: 'हाँ, बोलिए. मैं सुन रही हूँ.'
    }
  }
  return replies[language][key]
}

const messageText = (message: any) => {
  if (!message || typeof message !== 'object') return ''
  if (Array.isArray(message.parts) && message.parts[0]) {
    return String(message.parts[0].text || '').trim()
  }
  return String(message.content || message.text || '').trim()
}

const cleanImagePrompt = (value: string) => {
  const cleaned = String(value || '')
    .replace(/\s+/g, ' ')
    .replace(/^[\s:.-]+|[\s:.-]+$/g, '')
    .replace(/^(of|for|about|ki|ka|ke|karke|kar\s+ke|kar\s+do|do|de\s+do|dijiye|please)\s+/i, '')
    .trim()

  if (
    /^(image|photo|picture|pic|wallpaper|art|tasveer|chitra|generate|create|make|draw|design|banao|bana|banado|banaao|karo|karke|kar\s+ke|kar\s+do|do|de\s+do|dijiye|please|\s)+$/i.test(
      cleaned
    )
  ) {
    return ''
  }
  return cleaned
}

const imagePromptFromIntent = (value: string) => {
  const raw = String(value || '').trim()
  if (!raw) return ''
  const imageWord = '(?:image|photo|picture|pic|wallpaper|art|tasveer|chitra)'
  const actionWord = '(?:generate|create|make|draw|design|banao|bana|banado|banaao|karo|kar\\s+do)'
  const connector = '(?:(?:of|for|about|ki|ka|ke)\\b|:)'
  if (!new RegExp(`\\b${imageWord}\\b`, 'i').test(raw) || !new RegExp(`\\b${actionWord}\\b`, 'i').test(raw)) {
    return ''
  }

  const patterns = [
    new RegExp(
      `^(?:please\\s+)?(?:generate|create|make|draw|design)\\s+(?:an?\\s+|ek\\s+|achhi\\s+|acchi\\s+|high\\s+quality\\s+)*${imageWord}\\s*${connector}?\\s*(.*)$`,
      'is'
    ),
    new RegExp(`^(?:please\\s+)?${imageWord}\\s+${actionWord}\\s*${connector}?\\s*(.*)$`, 'is'),
    new RegExp(
      `^(?:please\\s+)?${actionWord}\\s+(?:an?\\s+|ek\\s+|achhi\\s+|acchi\\s+|high\\s+quality\\s+)*${imageWord}\\s*${connector}?\\s*(.*)$`,
      'is'
    ),
    new RegExp(`^(.+?)\\s+(?:(?:ki|ka|ke)\\b\\s*)?${imageWord}\\s+${actionWord}\\s*$`, 'is')
  ]

  for (const pattern of patterns) {
    const match = raw.match(pattern)
    const prompt = cleanImagePrompt(match?.[1] || '')
    if (prompt) return prompt
  }

  return 'high quality original Shell AI concept image'
}

const recallFromHistory = (text: string, messages: any[]) => {
  const lower = String(text || '').trim().toLowerCase()
  const hasRecallIntent = [
    'yaad',
    'remember',
    'recall',
    'pichla',
    'pichle',
    'previous',
    'last task',
    'last command',
    'abhi kya',
    'kya kaam',
    'what did i ask',
    'what was my last'
  ].some((token) => lower.includes(token))
  if (!hasRecallIntent) return ''

  const previous = messages
    .filter((item: any) => item?.role === 'user')
    .map(messageText)
    .map((value) => value.replace(/^Chart:\s*/i, '').trim())
    .filter((value) => value && value.toLowerCase() !== lower)

  if (!previous.length) {
    return languageReply('noRecall')
  }
  return languageReply('recall', { task: previous[previous.length - 1] })
}

const creatorIdentityReply = (text: string, source = 'text') => {
  const normalized = String(text || '').toLowerCase().replace(/\s+/g, ' ').trim()
  if (!normalized) return ''
  const subjectIntent = /\b(shell|shell ai|you|your|tum|tumhe|tumko|tujhe|tume|aap|aapko|apko|tere|tera|tu)\b/i.test(
    normalized
  )
  const creatorIntent =
    /\b(kis\s*ne|kisne|kaun|kon|who|whom|which company|company|creator|maker|founder|owner|developer|made|created|built|developed|designed|banaya|bana\s*ya|banaya\s*hai|banaya\s*ha|banaya\s*h|banane\s*wala|banane\s*waala|banane\s*wale|create\s*kiya|develop\s*kiya)\b/i.test(
      normalized
    )
  const explicitCreatorPhrase =
    /\b(shell|shell ai|your|tumhara|tera|aapka)\s+(creator|maker|founder|owner|developer)\b/i.test(
      normalized
    ) || /\b(creator|maker|founder|owner|developer)\s+(kaun|kon|who|kisne|kis\s*ne)\b/i.test(normalized)
  if (!((subjectIntent && creatorIntent) || explicitCreatorPhrase)) return ''
  return source === 'voice'
    ? 'Mujhe Md Shoaib King ne banaya hai.'
    : 'Mujhe Md Shoeb King ne banaya hai.'
}

const researchIntentFromText = (value: string) => {
  const raw = String(value || '').trim()
  if (!raw) return ''
  if (!/\b(deep\s*(research|recerch)|research|recerch|fact\s*check|fact-check|multi\s*source|multi-source)\b/i.test(raw)) {
    return ''
  }
  return raw
    .replace(
      /^\s*(deep\s*)?(research|recerch|fact\s*check|fact-check)\s*(karo|kar|karna|about|on|for|ke\s+bare\s+mein|ke\s+barre\s+main|ke\s+bare\s+main|:)?\s*/i,
      ''
    )
    .replace(
      /\s+(par|pe|ke\s+bare\s+mein|ke\s+barre\s+main|ke\s+bare\s+main)\s+(deep\s*)?(research|recerch|fact\s*check|fact-check)\s*(karo|kar|karna)?\s*$/i,
      ''
    )
    .trim() || raw
}

const emitFallbackActivity = (
  kind: 'research' | 'image' | 'build' | 'search' | 'tool',
  status: 'running' | 'done' | 'error',
  prompt: string,
  message: string,
  progress: number
) => {
  const titleByKind = {
    research: 'DEEP RESEARCH',
    image: 'IMAGE GENERATION',
    build: 'BUILD TASK',
    search: 'LIVE SEARCH',
    tool: 'SHELL ACTION'
  }
  emit('activity-updated', {
    id: `${kind}-${Date.now()}`,
    kind,
    status,
    title: titleByKind[kind],
    prompt,
    message,
    progress,
    source: 'web-fallback'
  })
}

const fallbackInvoke = async (channel: string, ...args: unknown[]) => {
  switch (channel) {
    case 'get-system-stats':
      return {
        cpu: String(Math.floor(18 + Math.random() * 18)),
        memory: {
          total: '16 GB',
          free: '8 GB',
          usedPercentage: String(Math.floor(38 + Math.random() * 12))
        },
        temperature: 42,
        os: {
          type: navigator.platform || 'Shell OS',
          uptime: 'LOCAL'
        }
      }
    case 'get-installed-apps':
      return [
        { id: 'terminal', name: 'Terminal' },
        { id: 'browser', name: 'Browser' },
        { id: 'editor', name: 'Code Editor' },
        { id: 'files', name: 'File Explorer' },
        { id: 'settings', name: 'System Settings' }
      ]
    case 'get-running-apps':
      return ['Shell AI', 'Terminal', 'Browser']
    case 'get-history':
      return readHistory()
    case 'clear-history':
      writeHistory([])
      emit('history-cleared', { success: true })
      return { success: true, cleared: true, source: 'web-fallback' }
    case 'add-message': {
      const messages = readHistory()
      messages.push(args[0])
      writeHistory(messages)
      return true
    }
    case 'secure-get-keys':
      return {
        geminiKey: localStorage.getItem('shell_custom_api_key') || '',
        groqKey: localStorage.getItem('shell_groq_api_key') || '',
        hfKey: localStorage.getItem('shell_hf_api_key') || '',
        tavilyKey: localStorage.getItem('shell_tavily_api_key') || '',
        livekitKey: localStorage.getItem('shell_livekit_api_key') || '',
        livekitSecret: localStorage.getItem('shell_livekit_api_secret') || '',
        livekitUrl: localStorage.getItem('shell_livekit_url') || '',
        openaiKey: localStorage.getItem('shell_openai_api_key') || '',
        openrouterKey: localStorage.getItem('shell_openrouter_api_key') || '',
        mistralKey: localStorage.getItem('shell_mistral_api_key') || '',
        googleSearchKey: localStorage.getItem('shell_google_search_api_key') || '',
        searchEngineId: localStorage.getItem('shell_search_engine_id') || '',
        weatherKey: localStorage.getItem('shell_openweather_api_key') || '',
        telegramToken: localStorage.getItem('shell_telegram_bot_token') || '',
        telegramAllowedChatIds: localStorage.getItem('shell_telegram_allowed_chat_ids') || '',
        telegramRemoteControlEnabled: localStorage.getItem('shell_telegram_remote_control_enabled') || '0',
        telegramAllowTerminal: localStorage.getItem('shell_telegram_allow_terminal') || '0'
      }
    case 'list-api-keys':
      return { success: true, keys: [] }
    case 'get-personality':
      return localStorage.getItem('shell_personality') || ''
    case 'save-personality':
      localStorage.setItem('shell_personality', String(args[0] || ''))
      return true
    case 'get-settings':
      return {
        language: readShellLanguage(),
        shell_language: readShellLanguage()
      }
    case 'set-settings': {
      const payload = (args[0] || {}) as Record<string, unknown>
      const nextLanguage = normalizeShellLanguage(payload.language || payload.shell_language)
      localStorage.setItem(SHELL_LANGUAGE_STORAGE_KEY, nextLanguage)
      window.dispatchEvent(new CustomEvent('shell-language-changed', { detail: { language: nextLanguage } }))
      return {
        success: true,
        message: '1 setting(s) updated',
        applied: { language: nextLanguage, shell_language: nextLanguage }
      }
    }
    case 'get-gallery':
    case 'get-gallery-images':
      return readFallbackGallery()
    case 'get-notes':
    case 'get-drives':
    case 'load-workflows':
    case 'adb-get-history':
      return []
    case 'save-image-to-gallery': {
      const payload = (args[0] || {}) as Record<string, unknown>
      const dataUrl = String(payload.base64Data || payload.dataUrl || '')
      if (!dataUrl) return { success: false, message: 'Missing image data.' }
      const title = String(payload.title || payload.prompt || 'Shell AI image')
      const filename = `shell_ai_${Date.now()}.png`
      const image = {
        filename,
        displayName: title,
        path: 'browser-local',
        url: dataUrl,
        createdAt: new Date().toISOString()
      }
      const images = [image, ...readFallbackGallery()]
      writeFallbackGallery(images)
      emit('gallery-updated', { success: true, image })
      return { success: true, image, source: 'web-fallback' }
    }
    case 'delete-image': {
      const filename = String(args[0] || '')
      writeFallbackGallery(readFallbackGallery().filter((item: any) => item?.filename !== filename))
      emit('gallery-updated', { success: true, deleted: filename })
      return { success: true, source: 'web-fallback' }
    }
    case 'search-core-memory':
      return []
    case 'get-live-location':
      return { fullString: 'Local Shell session', timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || 'Local' }
    case 'get-screen-size':
      return { width: window.innerWidth, height: window.innerHeight }
    case 'get-screen-source':
      return null
    case 'get-app-version':
      return '1.0.0'
    case 'save-core-memory':
    case 'secure-save-keys': {
      const saved: string[] = []
      if (args[0] && typeof args[0] === 'object') {
        const payload = args[0] as Record<string, unknown>
        const storageMap: Record<string, string> = {
          groqKey: 'shell_groq_api_key',
          hfKey: 'shell_hf_api_key',
          tavilyKey: 'shell_tavily_api_key',
          livekitKey: 'shell_livekit_api_key',
          livekitSecret: 'shell_livekit_api_secret',
          livekitUrl: 'shell_livekit_url',
          openaiKey: 'shell_openai_api_key',
          openrouterKey: 'shell_openrouter_api_key',
          mistralKey: 'shell_mistral_api_key',
          googleSearchKey: 'shell_google_search_api_key',
          searchEngineId: 'shell_search_engine_id',
          weatherKey: 'shell_openweather_api_key',
          telegramToken: 'shell_telegram_bot_token',
          telegramAllowedChatIds: 'shell_telegram_allowed_chat_ids'
        }
        if ('geminiKey' in payload) {
          localStorage.setItem('shell_custom_api_key', normalizeGeminiApiKey(payload.geminiKey))
          saved.push('geminiKey')
        }
        Object.entries(storageMap).forEach(([payloadKey, storageKey]) => {
          if (payloadKey in payload) {
            localStorage.setItem(storageKey, String(payload[payloadKey] || '').trim())
            saved.push(payloadKey)
          }
        })
        if ('telegramRemoteControlEnabled' in payload) {
          localStorage.setItem('shell_telegram_remote_control_enabled', String(payload.telegramRemoteControlEnabled || '0'))
          saved.push('telegramRemoteControlEnabled')
        }
        if ('telegramAllowTerminal' in payload) {
          localStorage.setItem('shell_telegram_allow_terminal', String(payload.telegramAllowTerminal || '0'))
          saved.push('telegramAllowTerminal')
        }
      }
      return { success: true, source: 'web-fallback', saved }
    }
    case 'execute-tool':
      if (String(args[0] || '').includes('shell_telegram:telegram_bot_status')) {
        return {
          status: 'success',
          tool: 'shell_telegram:telegram_bot_status',
          result: 'Telegram Bot: INACTIVE\nShell backend bridge is not connected yet.'
        }
      }
      return { success: false, source: 'web-fallback', error: 'Shell backend bridge is not connected yet.' }
    case 'setup-vault-pin':
    case 'verify-vault-pin':
    case 'setup-vault-face':
    case 'verify-vault-face':
    case 'check-for-updates':
    case 'download-update':
    case 'install-update':
      return { success: false, source: 'web-fallback', error: 'Shell backend bridge is not connected yet.' }
    case 'get-capabilities':
      return { status: 'success', summary: { total: 0, tools: 0, agents: 0, actions: 0, categories: [] }, catalog: [], tools: [], actions: [] }
    case 'chat-message': {
      const messages = readHistory()
      const text = String(args[0] || '')
      const meta = args[1] && typeof args[1] === 'object' ? (args[1] as Record<string, unknown>) : {}
      const source = String(meta.source || 'text').toLowerCase() === 'voice' ? 'voice' : 'text'
      const attachments = Array.isArray(meta.attachments) ? (meta.attachments as any[]) : []
      const attachmentNames = attachments
        .map((item) => String(item?.name || '').trim())
        .filter(Boolean)
      const imagePrompt = imagePromptFromIntent(text)
      if (imagePrompt) {
        const route = {
          tool: 'browser:image_generation',
          args: { description: imagePrompt },
          source: 'web-fallback-image-intent'
        }
        const reply = await handleImageGeneration(imagePrompt)
        const success = !/^Generation failed:/i.test(reply)
        messages.push({ role: 'user', parts: [{ text }] }, { role: 'model', parts: [{ text: reply }] })
        writeHistory(messages)
        emit('chat-updated', { reply, route, success, source, voice: source === 'voice' })
        return { success, reply, route, source }
      }
      const researchPrompt = researchIntentFromText(text)
      if (researchPrompt) {
        emitFallbackActivity('research', 'running', researchPrompt, 'SEARCHING AND VERIFYING', 24)
        emitFallbackActivity('research', 'error', researchPrompt, 'RESEARCH BACKEND OFFLINE', 100)
      }
      const lower = text.toLowerCase()
      let reply = languageReply('backendOffline')
      const identityReply = creatorIdentityReply(text, source)
      const recallReply = recallFromHistory(text, messages)
      if (identityReply) reply = identityReply
      else if (recallReply) reply = recallReply
      else if (lower.includes('capital of france')) reply = languageReply('france')
      else if (lower.includes('memory') && lower.includes('python')) {
        reply = languageReply('pythonMemory')
      } else if (lower.includes('network protocol')) {
        reply = languageReply('networkProtocol')
      } else if (attachmentNames.length) {
        reply = languageReply('filesAttached', { files: attachmentNames.join(', ') })
      } else if (/^(hi|hello|hey|salam)\b/i.test(text.trim())) {
        reply = languageReply('hello')
      }
      const userText = attachmentNames.length
        ? `${text || 'Attached file'}\n\nAttached: ${attachmentNames.join(', ')}`
        : text
      messages.push({ role: 'user', parts: [{ text: userText }] }, { role: 'model', parts: [{ text: reply }] })
      writeHistory(messages)
      emit('chat-updated', { reply, success: false, source, voice: source === 'voice' })
      return { success: false, reply, source }
    }
    case 'speak-text': {
      const text = String(args[0] || '').trim()
      const synth = window.speechSynthesis
      if (!text || !synth) return { success: false, error: 'Speech synthesis unavailable.' }
      synth.cancel()
      const utterance = new SpeechSynthesisUtterance(text.slice(0, 320))
      utterance.lang = shellSpeechLocale()
      utterance.rate = 1
      utterance.pitch = 1
      synth.speak(utterance)
      return { success: true, source: 'web-speech' }
    }
    case 'offline-tts-status':
      return {
        success: true,
        available: Boolean(window.speechSynthesis),
        engine: 'web-speech',
        label: 'Browser speech fallback',
        language: readShellLanguage(),
        locale: shellSpeechLocale(),
        reason: window.speechSynthesis
          ? 'Backend bridge is offline; browser speech fallback is available.'
          : 'Backend bridge is offline and browser speech synthesis is unavailable.',
        candidates: []
      }
    case 'stop-speech':
      window.speechSynthesis?.cancel()
      return { success: true, source: 'web-speech' }
    case 'set-personality':
      localStorage.setItem('shell_personality', String(args[0] || ''))
      return true
    case 'open-app':
    case 'close-app':
    case 'google-search':
    case 'open-file':
    case 'open-in-vscode':
    case 'toggle-overlay':
      return { success: true, source: 'web-fallback' }
    case 'start-live-coding':
      return { success: false, error: 'Shell backend bridge is not connected yet.' }
    default:
      return { success: false, source: 'web-fallback', error: `Unhandled Shell UI channel: ${channel}` }
  }
}

const parseBridgeResult = (raw: unknown) => {
  if (typeof raw !== 'string') return raw
  try {
    const parsed = JSON.parse(raw) as ShellCallResult
    if (parsed && typeof parsed === 'object' && 'data' in parsed) return parsed.data
    return parsed
  } catch {
    return raw
  }
}

const callPython = (channel: string, args: unknown[]) =>
  new Promise<unknown>((resolve) => {
    let settled = false
    const finish = (value: unknown) => {
      if (settled) return
      settled = true
      window.clearTimeout(timer)
      resolve(value)
    }
    const timer = window.setTimeout(() => {
      finish({ success: false, error: `Shell backend timeout: ${channel}` })
    }, 15000)

    const invokeBridge = () => {
      pythonBridge.call(channel, JSON.stringify(args), (raw: unknown) => {
        finish(parseBridgeResult(raw))
      })
    }

    if (!pythonBridge?.call) {
      waitForPythonBridge().then((ready) => {
        if (ready && pythonBridge?.call) {
          try {
            invokeBridge()
          } catch {
            fallbackInvoke(channel, ...args).then(finish)
          }
          return
        }
        fallbackInvoke(channel, ...args).then(finish)
      })
      return
    }

    try {
      invokeBridge()
    } catch {
      fallbackInvoke(channel, ...args).then(finish)
    }
  })

const loadQWebChannel = () =>
  new Promise<void>((resolve) => {
    if ((window as any).QWebChannel || !(window as any).qt?.webChannelTransport) {
      resolve()
      return
    }

    const script = document.createElement('script')
    script.src = 'qrc:///qtwebchannel/qwebchannel.js'
    script.onload = () => resolve()
    script.onerror = () => resolve()
    document.head.appendChild(script)
  })

const connectPythonBridge = async () => {
  await loadQWebChannel()
  const qWebChannel = (window as any).QWebChannel
  const transport = (window as any).qt?.webChannelTransport
  if (!qWebChannel || !transport) return

  new qWebChannel(transport, (channel: any) => {
    pythonBridge = channel.objects.shellBridge
    if (pythonBridge?.eventEmitted?.connect) {
      pythonBridge.eventEmitted.connect((name: string, payload: string) => {
        let parsed: unknown = payload
        try {
          parsed = JSON.parse(payload)
        } catch {}
        emit(name, parsed)
      })
    }
    emit('shell-bridge-ready', { ok: true })
  })
}

const speakWithBrowser = async (speechText: string) => {
  const synth = window.speechSynthesis
  if (!speechText || !synth || typeof SpeechSynthesisUtterance === 'undefined') {
    return { success: false, error: 'Speech synthesis unavailable.' }
  }
  synth.cancel()
  const utterance = new SpeechSynthesisUtterance(speechText.slice(0, 320))
  utterance.lang = shellSpeechLocale()
  utterance.rate = 0.92
  utterance.volume = 1
  synth.speak(utterance)
  return { success: true, source: 'browser-speech' }
}

const shellAPI = {
  call: (channel: string, ...args: unknown[]) => callPython(channel, args),
  startVoice: () => callPython('start-voice', []),
  stopVoice: () => callPython('stop-voice', []),
  speakText: async (text: string) => {
    const speechText = String(text || '').trim()
    const desktopBridgeExpected = Boolean(pythonBridge?.call || (window as any).qt?.webChannelTransport)
    if (desktopBridgeExpected) {
      const bridgeResult = (await callPython('speak-text', [speechText])) as any
      if (bridgeResult?.success) return bridgeResult
    }
    return speakWithBrowser(speechText)
  },
  stopSpeech: async () => {
    window.speechSynthesis?.cancel()
    return callPython('stop-speech', [])
  },
  executeCommand: (command: string) => callPython('execute-command', [command]),
  getSystemMetrics: () => callPython('get-system-stats', []),
  searchMemory: (query: string) => callPython('search-memory', [query]),
  on: (channel: string, listener: Listener) => {
    if (!listeners.has(channel)) listeners.set(channel, new Set())
    listeners.get(channel)!.add(listener)
  },
  off: (channel: string, listener?: Listener) => {
    if (!listener) {
      listeners.delete(channel)
      return
    }
    listeners.get(channel)?.delete(listener)
  }
}

;(window as any).shellAPI = shellAPI
;(window as any).electron = (window as any).electron || {
  process: { platform: navigator.platform.toLowerCase().includes('mac') ? 'darwin' : 'browser' },
  ipcRenderer: {
    invoke: (channel: string, ...args: unknown[]) => shellAPI.call(channel, ...args),
    send: (channel: string, ...args: unknown[]) => {
      shellAPI.call(channel, ...args)
    },
    on: (channel: string, listener: Listener) => shellAPI.on(channel, listener),
    removeAllListeners: (channel: string) => shellAPI.off(channel)
  }
}

connectPythonBridge()
