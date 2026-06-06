import Editor, { useMonaco } from '@monaco-editor/react'
import { useEffect } from 'react'

export default function LiveCodingEditor({ code, filename }: { code: string; filename: string }) {
  const monaco = useMonaco()

  useEffect(() => {
    if (!monaco) return
    monaco.editor.defineTheme('shell-dark', {
      base: 'vs-dark',
      inherit: true,
      rules: [{ token: 'comment', foreground: '10b981', fontStyle: 'italic' }],
      colors: { 'editor.background': '#00000000' }
    })
    monaco.editor.setTheme('shell-dark')
  }, [monaco])

  return (
    <Editor
      height="100%"
      language={filename.endsWith('.py') ? 'python' : 'typescript'}
      theme="shell-dark"
      value={code}
      options={{
        readOnly: true,
        minimap: { enabled: false },
        fontSize: 14,
        fontFamily: "'Fira Code', monospace"
      }}
    />
  )
}
