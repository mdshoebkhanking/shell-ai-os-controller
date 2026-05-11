<!-- SPDX-License-Identifier: Apache-2.0 -->

# Phase 8 Voice And Multimodal Future

Voice and multimodal systems should feel fast and natural while staying
modular. Speech, screen, image, and camera data are sensitive inputs and must
be permission-gated.

## Modalities

- text
- voice input
- voice output
- screenshots
- OCR
- images
- documents
- browser state
- terminal output
- future camera input

## Multimodal Flow

```text
input capture
  -> permission check
  -> modality parser
  -> context bundle
  -> agent/task router
  -> response stream
  -> optional voice output
```

## Voice Principles

- Text chat should not auto-play voice unless user enables it.
- Voice mode should stream as early as possible.
- Local low-latency TTS fallback should remain available.
- Missing microphone/audio dependencies must degrade gracefully.

## Screen And Image Safety

- Screen capture must be explicit.
- OCR output is untrusted input.
- Visual automation should preview actions before clicking.
- Camera integrations require separate permission prompts.

## Future Work

- unified multimodal context envelope
- low-latency streaming voice agent
- OCR-to-workflow routing
- screen-state memory
- multimodal tool marketplace permissions
