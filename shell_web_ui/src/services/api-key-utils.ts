const assignmentPattern = /^(?:export\s+|set\s+)?([A-Z_][A-Z0-9_]{1,63})\s*=\s*(.*)$/i

const stripWrappingQuotes = (value: string) => {
  let out = String(value || '').trim()
  while (
    out.length >= 2 &&
    out[0] === out[out.length - 1] &&
    (out[0] === '"' || out[0] === "'" || out[0] === '`')
  ) {
    out = out.slice(1, -1).trim()
  }
  return out
}

const isPlaceholderSecret = (value: string) => {
  const lower = value.trim().toLowerCase()
  return (
    !lower ||
    lower.startsWith('your_') ||
    lower.startsWith('replace_') ||
    lower === 'changeme' ||
    lower === 'change_me' ||
    lower === 'paste_key_here' ||
    lower === 'api_key' ||
    lower === 'token' ||
    lower === 'password' ||
    lower === 'none' ||
    lower === 'null' ||
    lower === 'undefined'
  )
}

export const normalizeSecretInput = (value: unknown, acceptedNames: string[]) => {
  let out = stripWrappingQuotes(String(value || ''))
  const match = out.match(assignmentPattern)
  if (match) {
    const pastedName = match[1].toUpperCase()
    const accepted = new Set(acceptedNames.map((item) => item.toUpperCase()))
    if (accepted.has(pastedName)) out = stripWrappingQuotes(match[2])
  }
  return isPlaceholderSecret(out) ? '' : out
}

export const normalizeGeminiApiKey = (value: unknown) =>
  normalizeSecretInput(value, ['GOOGLE_API_KEY', 'GEMINI_API_KEY'])
