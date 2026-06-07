const { contextBridge, ipcRenderer } = require('electron')

const listeners = new Map()

const emit = (channel, payload) => {
  const channelListeners = listeners.get(channel)
  if (!channelListeners) return
  for (const listener of Array.from(channelListeners)) {
    try {
      listener({ channel }, payload)
    } catch {
      // Renderer listeners should not break bridge delivery.
    }
  }
}

ipcRenderer.on('shell-bridge-event', (_event, event) => {
  if (!event || typeof event !== 'object') return
  emit(String(event.channel || ''), event.payload)
})

ipcRenderer.on('shell-bridge-ready', (_event, payload) => {
  emit('shell-bridge-ready', payload)
})

const ipcApi = {
  invoke: (channel, ...args) => ipcRenderer.invoke('shell-bridge-call', channel, args),
  send: (channel, ...args) => {
    ipcRenderer.invoke('shell-bridge-call', channel, args).catch(() => {})
  },
  on: (channel, listener) => {
    const name = String(channel || '')
    if (!listeners.has(name)) listeners.set(name, new Set())
    listeners.get(name).add(listener)
  },
  off: (channel, listener) => {
    const name = String(channel || '')
    if (!listener) {
      listeners.delete(name)
      return
    }
    listeners.get(name)?.delete(listener)
  },
  removeAllListeners: (channel) => {
    listeners.delete(String(channel || ''))
  }
}

contextBridge.exposeInMainWorld('electron', {
  process: { platform: process.platform },
  ipcRenderer: ipcApi
})

contextBridge.exposeInMainWorld('__shellElectronBridge', {
  call: (channel, args) => ipcRenderer.invoke('shell-bridge-call', channel, Array.isArray(args) ? args : []),
  on: ipcApi.on,
  off: ipcApi.off
})
