export type ShellLanguage = 'hinglish' | 'english' | 'hindi'

export const SHELL_LANGUAGE_STORAGE_KEY = 'shell_language'

export const SHELL_LANGUAGE_OPTIONS: Array<{
  id: ShellLanguage
  label: string
  hint: string
  instruction: string
  speechInstruction: string
}> = [
  {
    id: 'hinglish',
    label: 'HINGLISH',
    hint: 'Hindi + English natural mix',
    instruction: 'Reply in natural Hinglish: Hindi and English mixed casually. Keep answers clear and short.',
    speechInstruction: 'Speak in natural Hinglish with a Hindi-English mix.'
  },
  {
    id: 'english',
    label: 'ENGLISH',
    hint: 'Clean English replies',
    instruction: 'Reply in clear English only. Keep answers direct, concise, and practical.',
    speechInstruction: 'Speak in clear English.'
  },
  {
    id: 'hindi',
    label: 'HINDI',
    hint: 'Simple Hindi replies',
    instruction: 'Reply in simple Hindi. Use Devanagari only when it stays readable; otherwise use easy spoken Hindi.',
    speechInstruction: 'Speak in simple Hindi.'
  }
]

export const normalizeShellLanguage = (value: unknown): ShellLanguage => {
  const language = String(value || '').trim().toLowerCase()
  if (language === 'english' || language === 'hindi' || language === 'hinglish') return language
  return 'hinglish'
}

export const readShellLanguage = (): ShellLanguage => {
  try {
    return normalizeShellLanguage(window.localStorage?.getItem(SHELL_LANGUAGE_STORAGE_KEY))
  } catch {
    return 'hinglish'
  }
}

export const shellLanguageInstruction = (language = readShellLanguage()) =>
  SHELL_LANGUAGE_OPTIONS.find((option) => option.id === language)?.instruction ||
  SHELL_LANGUAGE_OPTIONS[0].instruction

export const shellSpeechInstruction = (language = readShellLanguage()) =>
  SHELL_LANGUAGE_OPTIONS.find((option) => option.id === language)?.speechInstruction ||
  SHELL_LANGUAGE_OPTIONS[0].speechInstruction

export const shellSpeechLocale = (language = readShellLanguage()) => {
  if (language === 'english') return 'en-US'
  if (language === 'hindi') return 'hi-IN'
  return 'hi-IN'
}
