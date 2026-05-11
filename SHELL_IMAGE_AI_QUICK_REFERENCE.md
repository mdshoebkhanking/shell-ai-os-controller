# 🎨 SHELL_IMAGE_AI - QUICK REFERENCE GUIDE

## 📋 AVAILABLE TOOLS (5 Total)

### **Primary Tools**

| Tool | Parameters | Example |
|------|------------|---------|
| `generate_image_tool` | description, device_type="pc", style="", use_ai_enhancement=True | `generate_image_tool("cyberpunk city", style="cyberpunk")` |
| `generate_image_batch_tool` | descriptions (list), style="", device_type="pc" | `generate_image_batch_tool(["cat", "dog", "bird"])` |
| `get_image_generation_status_tool` | - | `get_image_generation_status_tool()` |
| `clear_image_cache_tool` | - | `clear_image_cache_tool()` |
| `list_image_styles_tool` | - | `list_image_styles_tool()` |

---

## 🎨 STYLE PRESETS (10 Available)

| Style | Best For | Keywords Added |
|-------|----------|----------------|
| **photorealistic** | Product shots, portraits | "professional photography, studio lighting, 8k" |
| **anime** | Characters, landscapes | "studio ghibli, makoto shinkai, vibrant" |
| **cyberpunk** | Sci-fi, tech | "neon lights, futuristic, blade runner" |
| **fantasy** | Game art, book covers | "magical, ethereal, concept art" |
| **minimalist** | Logos, icons | "clean, simple, elegant, negative space" |
| **oil_painting** | Traditional art | "textured brush strokes, renaissance" |
| **watercolor** | Artistic renders | "soft edges, flowing colors, hand-painted" |
| **pixel_art** | Game assets | "8-bit, retro game, pixelated" |
| **concept_art** | Pre-production | "professional, artstation, digital painting" |
| **hyperrealistic** | High-end visuals | "8k, octane render, unreal engine 5" |

---

## 🎯 COMMON USE CASES

### **1. Desktop Wallpaper**
```python
await generate_image_tool(
    "beautiful mountain landscape at sunset",
    device_type="pc",
    style="photorealistic"
)
```

### **2. Mobile Wallpaper**
```python
await generate_image_tool(
    "anime character portrait",
    device_type="mobile",
    style="anime"
)
```

### **3. Social Media Post**
```python
await generate_image_tool(
    "futuristic technology concept",
    device_type="square",
    style="cyberpunk"
)
```

### **4. Batch Generation**
```python
await generate_image_batch_tool(
    descriptions=["lion", "tiger", "leopard", "cheetah"],
    style="photorealistic",
    device_type="square"
)
```

### **5. Quick Icon**
```python
await generate_image_tool(
    "shopping cart icon",
    device_type="square",
    style="minimalist",
    use_ai_enhancement=False
)
```

---

## ⚙️ CONFIGURATION

### **Device Types**
```python
"pc"      → 1216x832  (16:9 landscape)
"mobile"  → 832x1216  (9:16 portrait)
"square"  → 1024x1024 (1:1 square)
```

### **Rate Limits**
```python
Hourly: 20 generations
Daily: 100 generations
```

### **Dimension Limits**
```python
Min: 256x256
Max: 2048x2048
Aspect Ratio: 1:4 to 4:1
```

---

## 🔧 PROMPT ENGINEERING TIPS

### **Good Prompts**
```
✅ "cyberpunk city at night with neon lights"
✅ "cute anime girl with blue hair, studio ghibli style"
✅ "photorealistic portrait of a lion, professional photography"
✅ "minimalist logo for tech startup"
```

### **Bad Prompts**
```
❌ "cat" (too vague)
❌ "make something cool" (no direction)
❌ [NSFW content] (blocked)
❌ "text that says 'Hello World'" (text rendering poor)
```

### **Prompt Formula**
```
[Subject] + [Style] + [Lighting] + [Composition] + [Quality]

Example:
"Majestic lion" + "photorealistic" + "golden hour lighting" + 
"rule of thirds" + "8k resolution, masterpiece"
```

---

## 📊 STATUS CHECKS

### **Check Rate Limits**
```python
status = await get_image_generation_status_tool()
# Returns:
# ⏱️ Hourly: 2/20 (18 remaining)
# 📅 Daily: 2/100 (98 remaining)
```

### **List Available Styles**
```python
styles = await list_image_styles_tool()
# Returns all 10 presets with descriptions
```

### **Clear Cache**
```python
await clear_image_cache_tool()
# Clears all cached images
```

---

## 🐛 TROUBLESHOOTING

### **Issue: "All providers failed"**
```python
# Check API keys in .env
HUGGINGFACE_API_KEY=your_key_here
GOOGLE_API_KEY=your_key_here

# Wait for rate limit reset
await get_image_generation_status_tool()
```

### **Issue: "Quota exceeded"**
```python
# Google API quota exhausted (common)
# Solution: Image generation will still work without prompt upscaling
# Or upgrade Google API plan
```

### **Issue: Slow generation**
```python
# Normal: 10-30 seconds per image
# If slower, check:
# 1. Internet connection
# 2. API provider status
# 3. Image dimensions (smaller = faster)
```

### **Issue: Poor quality**
```python
# Try:
# 1. Add style preset: style="photorealistic"
# 2. Enable AI enhancement: use_ai_enhancement=True
# 3. Be more specific in prompt
# 4. Increase dimensions (up to 2048x2048)
```

---

## 💾 FILE LOCATIONS

### **Generated Images**
```
Windows: C:\Users\<Username>\Pictures\Shell_Generated\
Mac/Linux: ~/Pictures/Shell_Generated/
```

### **Cache Location**
```
.shell_image_cache/
```

### **Log File**
```
shell_image_ai.log
```

---

## 🔌 API KEYS REQUIRED

### **Required (.env)**
```env
# Optional but recommended
HUGGINGFACE_API_KEY=hf_xxx

# For prompt enhancement (optional)
GOOGLE_API_KEY=AIzaSy...

# For premium generation (optional)
REPLICATE_API_KEY=r8_...
```

### **Get API Keys**
- **HuggingFace:** https://huggingface.co/settings/tokens
- **Google Gemini:** https://makersuite.google.com/app/apikey
- **Replicate:** https://replicate.com/account/api-tokens

---

## 📈 BEST PRACTICES

### **1. Use Style Presets**
```python
# ✅ Better
await generate_image_tool("cat", style="anime")

# ❌ Vague
await generate_image_tool("cat")
```

### **2. Enable AI Enhancement**
```python
# ✅ Better quality prompts
await generate_image_tool("landscape", use_ai_enhancement=True)

# ❌ Raw prompts only
await generate_image_tool("landscape", use_ai_enhancement=False)
```

### **3. Batch Similar Requests**
```python
# ✅ Efficient
await generate_image_batch_tool(["cat", "dog", "bird"], style="anime")

# ❌ Multiple calls
await generate_image_tool("cat", style="anime")
await generate_image_tool("dog", style="anime")
await generate_image_tool("bird", style="anime")
```

### **4. Check Rate Limits**
```python
# ✅ Before batch generation
status = await get_image_generation_status_tool()
print(f"Remaining: {status['hourly_remaining']}")
```

### **5. Use Cache**
```python
# ✅ Same prompt returns cached result
await generate_image_tool("sunset")  # Generates
await generate_image_tool("sunset")  # Returns cached (instant)
```

---

## 🎯 ADVANCED USAGE

### **Custom Dimensions**
```python
# Modify Config class
Config.DEFAULT_WIDTH = 1536
Config.DEFAULT_HEIGHT = 1024
```

### **Add Custom Style**
```python
StylePresets.PRESETS["my_style"] = {
    "prompt_suffix": "my custom keywords",
    "negative_prompt": "what to avoid"
}
```

### **Adjust Rate Limits**
```python
Config.MAX_GENERATIONS_PER_HOUR = 50
Config.MAX_GENERATIONS_PER_DAY = 200
```

---

## 📊 PERFORMANCE EXPECTATIONS

| Task | Expected Time |
|------|---------------|
| **Simple Generation** | 10-20s |
| **With AI Enhancement** | 15-30s |
| **Batch (5 images)** | 60-90s |
| **Cache Hit** | <1s |
| **Status Check** | <1s |

---

## 🆘 QUICK HELP

```python
# Generate image
await generate_image_tool("your prompt here")

# With style
await generate_image_tool("prompt", style="cyberpunk")

# For mobile
await generate_image_tool("prompt", device_type="mobile")

# Batch generate
await generate_image_batch_tool(["prompt1", "prompt2"])

# Check status
await get_image_generation_status_tool()

# List styles
await list_image_styles_tool()

# Clear cache
await clear_image_cache_tool()
```

---

**Quick Reference v10000** | Last Updated: 2026-03-01
