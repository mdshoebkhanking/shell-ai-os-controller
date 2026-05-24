import { useEffect, useMemo, useRef, useState } from 'react'
import {
  RiCommandLine,
  RiPlayLine,
  RiRefreshLine,
  RiSearchLine,
  RiShieldFlashLine,
  RiToolsLine
} from 'react-icons/ri'

interface ToolParam {
  name: string
  annotation?: string
  required?: boolean
  default?: unknown
}

interface ToolItem {
  id: string
  name?: string
  title?: string
  category?: string
  kind?: string
  risk?: string
  description?: string
  params?: ToolParam[]
}

interface CapabilityPayload {
  status?: string
  summary?: Record<string, any>
  catalog?: ToolItem[]
  tools?: ToolItem[]
  actions?: ToolItem[]
  error?: string
}

const glassPanel = 'bg-zinc-950/40 backdrop-blur-xl border border-white/5 rounded-2xl shadow-xl'

const defaultArgsFor = (tool: ToolItem | null) => {
  if (!tool?.params?.length) return '{}'
  const args = Object.fromEntries(
    tool.params.map((param) => [
      param.name,
      param.default !== null && param.default !== undefined ? param.default : ''
    ])
  )
  return JSON.stringify(args, null, 2)
}

const ControlCenter = () => {
  const [payload, setPayload] = useState<CapabilityPayload>({})
  const [selected, setSelected] = useState<ToolItem | null>(null)
  const [query, setQuery] = useState('')
  const [category, setCategory] = useState('all')
  const [argsText, setArgsText] = useState('{}')
  const [result, setResult] = useState('')
  const [loading, setLoading] = useState(true)
  const [running, setRunning] = useState(false)
  const argsRef = useRef<HTMLTextAreaElement>(null)

  const loadCatalog = async () => {
    setLoading(true)
    try {
      const data = (await window.shellAPI?.call('get-capabilities')) as CapabilityPayload
      setPayload(data || {})
      const first = (data?.catalog || data?.tools || [])[0] || null
      setSelected(first)
      setArgsText(defaultArgsFor(first))
    } catch (error) {
      setPayload({ status: 'error', error: String(error), catalog: [] })
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadCatalog()
  }, [])

  const catalog = useMemo(() => payload.catalog || payload.tools || [], [payload])
  const categories = useMemo(
    () => ['all', ...Array.from(new Set(catalog.map((item) => item.category || 'general'))).sort()],
    [catalog]
  )

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase()
    return catalog
      .filter((item) => category === 'all' || (item.category || 'general') === category)
      .filter((item) => {
        if (!needle) return true
        const haystack = `${item.id} ${item.title || ''} ${item.description || ''}`.toLowerCase()
        return haystack.includes(needle)
      })
      .slice(0, 180)
  }, [catalog, category, query])

  const selectTool = (tool: ToolItem) => {
    setSelected(tool)
    setArgsText(defaultArgsFor(tool))
    setResult('')
  }

  const executeSelected = async () => {
    if (!selected || running) return
    setRunning(true)
    try {
      const currentArgsText = argsRef.current?.value ?? argsText
      const parsed = JSON.parse(currentArgsText || '{}')
      const response = await window.shellAPI?.call('execute-tool', selected.id, parsed)
      setResult(JSON.stringify(response, null, 2))
    } catch (error) {
      setResult(`Execution error: ${String(error)}`)
    } finally {
      setRunning(false)
    }
  }

  const summary = payload.summary || {}

  return (
    <div className="h-full w-full p-4 bg-white/2 grid grid-cols-12 gap-4 overflow-hidden animate-in fade-in zoom-in duration-300">
      <div className="col-span-12 lg:col-span-4 flex flex-col gap-4 min-h-0">
        <div className={`${glassPanel} p-4 shrink-0`}>
          <div className="flex items-center justify-between border-b border-white/10 pb-3">
            <span className="text-[11px] font-bold tracking-widest text-zinc-300 flex items-center gap-2">
              <RiToolsLine className="text-emerald-400" /> BACKEND CONTROL
            </span>
            <button
              aria-label="Refresh backend tools"
              onClick={loadCatalog}
              className="cursor-pointer p-2 rounded-lg border border-white/10 text-zinc-400 hover:text-emerald-300 hover:border-emerald-500/30 transition-all"
            >
              <RiRefreshLine size={15} />
            </button>
          </div>

          <div className="grid grid-cols-4 gap-2 mt-4">
            {[
              ['TOTAL', summary.total ?? catalog.length],
              ['TOOLS', summary.tools ?? 0],
              ['AGENTS', summary.agents ?? 0],
              ['ACTIONS', summary.actions ?? 0]
            ].map(([label, value]) => (
              <div key={label} className="rounded-xl bg-black/40 border border-white/5 p-3">
                <div className="text-[8px] font-mono text-zinc-600 tracking-widest">{label}</div>
                <div className="text-lg font-black text-emerald-300 font-mono">{String(value)}</div>
              </div>
            ))}
          </div>
        </div>

        <div className={`${glassPanel} p-4 flex-1 min-h-0 flex flex-col gap-3`}>
          <div className="flex gap-2">
            <div className="flex-1 flex items-center gap-2 bg-black/50 border border-white/10 rounded-lg px-3">
              <RiSearchLine className="text-zinc-500" />
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search tools, agents, actions..."
                className="min-w-0 flex-1 bg-transparent py-2.5 text-[11px] font-mono text-zinc-200 outline-none placeholder:text-zinc-700"
              />
            </div>
          </div>

          <div className="flex gap-2 overflow-x-auto scrollbar-small pb-1">
            {categories.map((item) => (
              <button
                key={item}
                onClick={() => setCategory(item)}
                className={`cursor-pointer shrink-0 px-3 py-1.5 rounded-md text-[9px] font-bold tracking-widest uppercase border transition-all ${
                  category === item
                    ? 'bg-emerald-500/20 border-emerald-500/30 text-emerald-300'
                    : 'bg-black/30 border-white/10 text-zinc-500 hover:text-zinc-200'
                }`}
              >
                {item}
              </button>
            ))}
          </div>

          <div className="flex-1 min-h-0 overflow-y-auto scrollbar-small space-y-2 pr-1">
            {loading ? (
              <div className="text-[11px] font-mono text-zinc-500">Loading backend catalog...</div>
            ) : filtered.length === 0 ? (
              <div className="text-[11px] font-mono text-zinc-500">No matching backend option.</div>
            ) : (
              filtered.map((tool) => (
                <button
                  key={tool.id}
                  onClick={() => selectTool(tool)}
                  className={`cursor-pointer w-full text-left rounded-xl border p-3 transition-all ${
                    selected?.id === tool.id
                      ? 'bg-emerald-500/10 border-emerald-500/30'
                      : 'bg-black/30 border-white/5 hover:border-white/15'
                  }`}
                >
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-[11px] font-bold text-zinc-100 tracking-wide">
                      {tool.title || tool.name || tool.id}
                    </span>
                    <span
                      className={`text-[8px] font-mono px-2 py-0.5 rounded border ${
                        tool.risk === 'guarded'
                          ? 'text-orange-300 border-orange-500/20 bg-orange-500/10'
                          : 'text-emerald-300 border-emerald-500/20 bg-emerald-500/10'
                      }`}
                    >
                      {tool.risk || 'normal'}
                    </span>
                  </div>
                  <div className="mt-1 text-[9px] font-mono text-zinc-500 truncate">{tool.id}</div>
                </button>
              ))
            )}
          </div>
        </div>
      </div>

      <div className="col-span-12 lg:col-span-8 min-h-0">
        <div className={`${glassPanel} h-full p-5 flex flex-col gap-4 overflow-y-auto scrollbar-small`}>
          {selected ? (
            <>
              <div className="border-b border-white/10 pb-4">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <div className="text-xl font-black tracking-widest text-white">
                      {selected.title || selected.name}
                    </div>
                    <div className="mt-1 text-[10px] font-mono text-zinc-500">{selected.id}</div>
                  </div>
                  <div className="flex items-center gap-2 text-[9px] font-mono">
                    <span className="px-2 py-1 rounded border border-white/10 text-zinc-400">
                      {selected.kind || 'tool'}
                    </span>
                    <span className="px-2 py-1 rounded border border-emerald-500/20 text-emerald-300">
                      {selected.category || 'general'}
                    </span>
                  </div>
                </div>
                <p className="mt-3 text-sm text-zinc-400 leading-relaxed">
                  {selected.description || 'No description available.'}
                </p>
              </div>

              <div className="grid grid-cols-1 2xl:grid-cols-2 gap-4">
                <div className="flex flex-col gap-3">
                  <div className="text-[10px] font-bold tracking-widest text-zinc-400 flex items-center gap-2">
                    <RiCommandLine className="text-emerald-400" /> PARAMETERS JSON
                  </div>
                  <textarea
                    ref={argsRef}
                    aria-label="Backend tool parameters JSON"
                    value={argsText}
                    onChange={(event) => setArgsText(event.target.value)}
                    className="min-h-52 md:min-h-64 resize-none rounded-xl bg-black/60 border border-white/10 p-4 font-mono text-xs text-zinc-100 outline-none focus:border-emerald-500/40 scrollbar-small"
                  />
                  <button
                    aria-label="Execute selected backend tool"
                    onClick={executeSelected}
                    disabled={running}
                    className="cursor-pointer h-11 rounded-xl bg-emerald-500 text-black text-xs font-black tracking-widest flex items-center justify-center gap-2 hover:bg-emerald-300 disabled:opacity-50 transition-all"
                  >
                    <RiPlayLine size={16} /> {running ? 'RUNNING' : 'EXECUTE'}
                  </button>
                </div>

                <div className="flex flex-col gap-3">
                  <div className="text-[10px] font-bold tracking-widest text-zinc-400 flex items-center gap-2">
                    <RiShieldFlashLine className="text-emerald-400" /> RESULT / READINESS
                  </div>
                  <pre className="min-h-52 md:min-h-64 overflow-auto scrollbar-small rounded-xl bg-black/60 border border-white/10 p-4 text-[11px] leading-relaxed text-zinc-300 whitespace-pre-wrap">
                    {result ||
                      JSON.stringify(
                        {
                          params: selected.params || [],
                          risk: selected.risk || 'normal',
                          file: (selected as any).file,
                          line: (selected as any).line
                        },
                        null,
                        2
                      )}
                  </pre>
                </div>
              </div>
            </>
          ) : (
            <div className="h-full grid place-items-center text-zinc-600 font-mono">
              Select a backend option.
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default ControlCenter
