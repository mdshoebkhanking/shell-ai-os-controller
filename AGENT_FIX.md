# Shell Agent Fix - Gemini Realtime Model Issue

## Problem
The agent was starting but immediately shutting down with the following error:
```
DEBUG:livekit.agents:session closed {"reason": "user_initiated", "error": null}
```

## Root Cause
The model name `gemini-2.5-flash-native-audio-latest` is **NOT a valid model name**. 

The `-latest` suffix is not supported by the Gemini Realtime API. This caused the session to fail immediately after starting.

## Solution

### 1. Updated `.env` file
Changed from:
```env
GEMINI_MODEL=gemini-2.5-flash-native-audio-latest
```

To:
```env
GEMINI_MODEL=gemini-2.5-flash-native-audio-preview-12-2025
```

### 2. Updated `agent.py`
- Added proper model validation to skip invalid model names with `-latest` suffix
- Added better error handling to detect policy violations and model-not-found errors
- Updated the fallback model list to use only supported models

### Supported Gemini Realtime Audio Models (as of 2026)
1. `gemini-2.5-flash-native-audio-preview-12-2025` ✅ **Primary (Recommended)**
2. `gemini-2.5-flash-native-audio-preview-09-2025` ✅ Fallback
3. `gemini-live-2.5-flash-native-audio` ✅ Vertex AI GA model
4. `gemini-live-2.5-flash-preview-native-audio-09-2025` (Preview)
5. `gemini-live-2.5-flash-preview-native-audio` (Legacy)

## How to Test

### Option 1: Run via Batch File (Recommended)
```bash
start_shell.bat
```

This will launch:
- Shell Hub (web server)
- MCP Server
- Shell Agent (console mode)
- Shell UI

### Option 2: Run Agent Directly
```bash
# Activate virtual environment first
venv\Scripts\activate

# Run in console mode
python agent.py console
```

## Expected Output

When working correctly, you should see:
```
✅ Connected to LiveKit room successfully
🛠️  AGENT TOOLS LOADED (105): [...]
🧠 Long-Term Memory Injected into System Context.
✅ Connected to Shell Hub: http://127.0.0.1:5000
[SYSTEM] INITIALIZING SHELL ULTRA PRO MAX...
[SUCCESS] SYSTEM ONLINE. WAITING FOR MASTER MD SHOAIB KING.
🚀 Initializing Realtime Session: gemini-2.5-flash-native-audio-preview-12-2025 (API: v1alpha)
✅ Realtime model 'gemini-2.5-flash-native-audio-preview-12-2025' started successfully (Optimized Mode).
✅ Session ready. Entering main loop...
```

## Troubleshooting

### If you still see session closing immediately:

1. **Check API Key**: Ensure your `GOOGLE_API_KEY` is valid and has Gemini API access
   ```bash
   python check_gemini.py
   ```

2. **Check Model Availability**: Some models may not be available in all regions
   - Try switching to a different model from the supported list
   - Update `.env`: `GEMINI_MODEL=gemini-2.5-flash-native-audio-preview-09-2025`

3. **Check API Version**: 
   - `v1alpha` - For preview models
   - `v1beta` - For GA models (if using Vertex AI)

4. **Enable Debug Logging**:
   Add to `.env`:
   ```env
   LOG_LEVEL=DEBUG
   ```

5. **Check LiveKit Connection**:
   Verify your `LIVEKIT_URL`, `LIVEKIT_API_KEY`, and `LIVEKIT_API_SECRET` are correct

## Files Modified
- `.env` - Updated GEMINI_MODEL
- `agent.py` - Added model validation and better error handling

## References
- [Gemini API Models](https://ai.google.dev/gemini-api/docs/models)
- [LiveKit Plugins Google](https://github.com/livekit/agents/tree/main/livekit-plugins/livekit-plugins-google)
- [Gemini Live API Documentation](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/models/gemini/2-5-flash-live-api)
