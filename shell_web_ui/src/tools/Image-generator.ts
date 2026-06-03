import { InferenceClient } from '@huggingface/inference'

const DEFAULT_IMAGE_PROMPT = 'high quality original Shell AI concept image'

const emitImageGenerationEvent = (detail: Record<string, unknown>) => {
  window.dispatchEvent(new CustomEvent('image-gen', { detail }))
}

const readHuggingFaceApiKey = async () => {
  const localKey = localStorage.getItem('shell_hf_api_key') || ''
  if (localKey.trim()) return localKey.trim()

  try {
    const secureKeys = await window.electron?.ipcRenderer.invoke('secure-get-keys')
    return String(secureKeys?.hfKey || '').trim()
  } catch {
    return ''
  }
}

const safeErrorMessage = (value: unknown) =>
  String(value instanceof Error ? value.message : value || 'Image generation failed.')
    .replace(/hf_[A-Za-z0-9_-]+/g, '[redacted]')
    .replace(/sk-[A-Za-z0-9_-]+/g, '[redacted]')

export const handleImageGeneration = async (prompt: string) => {
  const normalizedPrompt = String(prompt || '').trim() || DEFAULT_IMAGE_PROMPT
  emitImageGenerationEvent({ prompt: normalizedPrompt, loading: true, url: '' })

  try {
    const HF_API_KEY = await readHuggingFaceApiKey()

    if (!HF_API_KEY.trim()) {
      throw new Error(
        'Missing Hugging Face API Key. Please enter it in the Command Center Vault (Settings Tab).'
      )
    }

    const client = new InferenceClient(HF_API_KEY)

    const imageBlob: any = await client.textToImage({
      model: 'black-forest-labs/FLUX.1-schnell',
      inputs: normalizedPrompt
    })

    const imageUrl = URL.createObjectURL(imageBlob)

    emitImageGenerationEvent({
      url: imageUrl,
      prompt: normalizedPrompt,
      loading: false,
      error: false,
      saved: false
    })

    return 'Visual generated successfully using FLUX.'
  } catch (e: any) {

    let errorMessage = safeErrorMessage(e)

    if (errorMessage.includes('503') || errorMessage.includes('loading')) {
      errorMessage = 'Model is warming up (Free Tier). Please try again in 20 seconds.'
    }

    emitImageGenerationEvent({
      url: '',
      prompt: normalizedPrompt,
      loading: false,
      error: true,
      errorMessage: errorMessage
    })

    return `Generation failed: ${errorMessage}`
  }
}
