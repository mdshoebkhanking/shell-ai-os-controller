/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_GEMINI_API_KEY: string
  readonly MAIN_VITE_GEMINI_API_KEY: string
  readonly VITE_SHELL_WEB_USE_GEMINI?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}

interface Window {
  shellAPI?: {
    call: (channel: string, ...args: unknown[]) => Promise<unknown>
    startVoice: () => Promise<unknown>
    stopVoice: () => Promise<unknown>
    speakText: (text: string) => Promise<unknown>
    stopSpeech: () => Promise<unknown>
    executeCommand: (command: string) => Promise<unknown>
    getSystemMetrics: () => Promise<unknown>
    searchMemory: (query: string) => Promise<unknown>
    on: (channel: string, listener: (event: unknown, payload?: unknown) => void) => void
    off: (channel: string, listener?: (event: unknown, payload?: unknown) => void) => void
  }
  electron?: {
    process?: { platform?: string }
    ipcRenderer: {
      invoke: (channel: string, ...args: unknown[]) => Promise<any>
      send: (channel: string, ...args: unknown[]) => void
      on: (channel: string, listener: (event: unknown, payload?: unknown) => void) => void
      off: (channel: string, listener?: (event: unknown, payload?: unknown) => void) => void
      removeAllListeners: (channel: string) => void
    }
  }
}
