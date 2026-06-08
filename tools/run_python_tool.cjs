#!/usr/bin/env node

const { spawnSync } = require('node:child_process')

const [, , script, ...scriptArgs] = process.argv

if (!script) {
  console.error('Usage: node tools/run_python_tool.cjs <script.py> [...args]')
  process.exit(2)
}

const candidates = [
  process.env.PYTHON ? { command: process.env.PYTHON, args: [] } : null,
  { command: 'python', args: [] },
  { command: 'python3', args: [] },
  { command: 'py', args: ['-3'] }
].filter(Boolean)

let missingReason = ''

for (const candidate of candidates) {
  const version = spawnSync(candidate.command, [...candidate.args, '--version'], {
    encoding: 'utf8',
    stdio: ['ignore', 'pipe', 'pipe']
  })
  if (version.error || version.status !== 0) {
    missingReason = version.error?.message || version.stderr || version.stdout || missingReason
    continue
  }

  const result = spawnSync(candidate.command, [...candidate.args, script, ...scriptArgs], {
    stdio: 'inherit'
  })
  if (result.error) {
    console.error(result.error.message)
    process.exit(1)
  }
  process.exit(result.status ?? 0)
}

console.error(`No Python interpreter found for ${script}. ${String(missingReason || '').trim()}`)
process.exit(127)
