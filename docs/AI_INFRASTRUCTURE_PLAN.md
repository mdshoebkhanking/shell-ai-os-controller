<!-- SPDX-License-Identifier: Apache-2.0 -->

# AI Infrastructure Plan

Shell should support modern AI infrastructure without locking users into one
provider or one deployment model.

## Provider Strategy

Supported provider types:

- Cloud text models.
- Cloud multimodal models.
- Local LLMs.
- Local embeddings.
- Local TTS/STT.
- Realtime voice providers.
- Specialist APIs for image, search, OCR, and automation.

## Runtime Contract

Every AI runtime should eventually expose:

```text
runtime_id
provider
model
capabilities
cost_profile
latency_profile
privacy_profile
health_state
supports_streaming
supports_tools
supports_images
supports_audio
```

## Model Selection Policy

Selection should consider:

- Task type.
- Privacy requirements.
- Online/offline state.
- Latency target.
- User profile.
- Cost budget.
- Memory pressure.
- Provider health.

Example routing:

| Task | Preferred Runtime |
| --- | --- |
| Short chat | Fast cloud or local lightweight model |
| Coding/refactor | Coding-strong model with validation |
| Private local file summary | Local model when available |
| Voice response | Low-latency realtime or local TTS fallback |
| Screenshot reasoning | Multimodal model or OCR + text model |

## Memory Systems

Memory should remain layered:

- Active conversation memory.
- Project memory.
- Tool success/failure memory.
- User preferences.
- Incident memory.
- Semantic retrieval index.

Enterprise rule: memory export, deletion, and reset must be explicit and visible.

## Agent Systems

Agents should be role-based, bounded, and observable:

- Planner.
- Executor.
- Validator.
- Researcher.
- Summarizer.
- Recovery helper.

No recursive self-spawning by default.

## Automation Pipelines

Pipelines should support:

- Dry-run preview.
- Permission requirements.
- Retry policy.
- Timeout.
- Rollback link.
- Execution trace.

## Multimodal Readiness

Prepare for:

- Screenshot understanding.
- OCR routing.
- Voice input.
- Audio output.
- PDF/document extraction.
- Browser state.
- Terminal output.

Every modality should publish structured context, not raw private data by
default.

## Implementation Priority

1. Runtime descriptor interface.
2. Provider health scoring.
3. Streaming-first text path.
4. Local TTS/STT profile.
5. Memory deletion/export controls.
6. Tool-call validation layer.
7. Multimodal context normalization.
