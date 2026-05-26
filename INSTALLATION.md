# Shell AI - Simple Install Guide

Recommended flow:

1. Windows: double-click `ONE_CLICK_INSTALL.bat`.
2. macOS: double-click `ONE_CLICK_INSTALL.command`.
3. Wait until setup finishes. It creates `.shellai_venv`, installs backend dependencies, UI dependencies from `shell_ui/requirements_ui.txt`, browser runtime, ffmpeg/OCR where possible, and writes `.env`.
4. Start Shell:
   - Windows: double-click `Start_ShellAI.bat`
   - macOS: double-click `start_shellai.command`
5. If something breaks, run:
   - Windows: `Repair_ShellAI.bat`
   - macOS: `repair_shellai.command`

Health report: `.shell_runtime/install_health.json`
Logs: `.shell_runtime/logs/`

The old detailed guide is kept below for API key setup and manual troubleshooting.

# Shell AI - Detailed Setup Notes

Welcome.
Shell AI OS Controller 1.0.0 is a desktop AI assistant project created by `mdshoebking`.
Agar aapko **ABC** bhi nahi aati coding ki, tab bhi aap ise 10 minute mein chala lenge.

Bas niche diye gaye steps ko **ek-ek karke** follow karein. Dimag lagane ki zarurat nahi hai, sab likha hai!

---

# 🛑 PART 1: Softwares Download (Sabse Pehle)

Shell AI ko chalane ke liye aapke computer ko 3 cheezein sikhani padengi: `Python`, `Node.js`, aur `Tesseract`.
Inko download karke install karna hai.

### 1️⃣ Python (Computer Ka Dimag) 🧠
Ye sabse zaruri hai. Agar ye galat hua toh kuch nahi chalega.
1.  **Download Link**: 👉 [Yahan Click Karein](https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe)
2.  Setup File Open karein.
3.  ⚠️ **WARNING**: Niche ek chota sa box hoga: **"Add python.exe to PATH"**.
    - Isko ✅ **TICK** karna **BOHOT ZARURI** hai.
    - Agar tick nahi kiya toh error aayega!
4.  Ab **"Install Now"** par click karein aur wait karein.

### 2️⃣ Node.js (Shell Web UI ke liye zaruri) ⚡
Ye React Shell Web UI ko build karne ke liye chahiye. Node.js `20.19+` ya
`22.12+` use karein. Agar npm missing ya old hoga toh setup
`shell_web_ui/dist/index.html is missing` dikha sakta hai.
1.  **Download Link**: 👉 [Yahan Click Karein](https://nodejs.org/en/download)
2.  File open karein.
3.  **Next -> Next -> Next -> Install**.

### 3️⃣ Tesseract (Computer Ki Aankhein) 👁️
Ye Shell ko aapki screen dekhne mein madad karta hai.
1.  **Download Link**: 👉 [Yahan Click Karein](https://github.com/UB-Mannheim/tesseract/wiki)
2.  Page par niche jayen aur **`tesseract-ocr-w64-setup.exe`** dhund kar download karein.
3.  Install karein (English language select karein).

---

# 🚀 PART 2: Auto-Setup (Magic Button)

Ab aapko mehnat nahi karni. Humne ek magic file banayi hai.

1.  Apne **Shell AI Folder** mein jayen (jo aapne download kiya hai).
2.  Wahan ek file dhundhein: **`ONE_CLICK_INSTALL.bat`** ⚙️
3.  Uspar **Double Click** karein.
4.  Ek kali window (Black Screen) khulegi.
    - Ye khud internet se saare tools download karegi.
    - Ismein **5 se 15 minute** lag sakte hain (Internet speed par depend karta hai).
    - Bas dekhte rahein.
5.  Jab wo puche **"ENTER YOUR GOOGLE GEMINI API KEY"**, tab ruk jayein aur niche **PART 4** padhein key lene ke liye.

---

# 🎨 PART 3: Holographic Display (Iron Man Look)

Agar aapko wo cool transparent display chahiye:

1.  Main folder ke andar **`shell_ui`** folder mein jayen.
2.  **`build_exe.bat`** file par double click karein.
3.  Wait karein jab tak likha na aaye: **"BUILD SUCCESSFUL"**.
4.  Window band kar dein.

---

# 🔑 PART 4: THE API KEY BIBLE (Khazana) 💰

Shell AI ko chalane ke liye kuch "Special Passwords" (API Keys) chahiye hote hain.
Ye sab **FREE** hain. Aapko bas signup karke copy-paste karna hai `.env` file mein.

Apne folder mein **`.env`** file ko Notepad se open karein aur niche di gayi keys bhar dein.

## 🟢 SECTION A: Must Have (Iske Bina Nahi Chalega)

### 1. Google Gemini Key (The Brain) 🧠
Ye Shell ka main dimag hai.
- **Link**: [Google AI Studio](https://aistudio.google.com/app/apikey)
- **Steps**:
  1. Link par click karein aur Gmail se login karein.
  2. Blue button dabayein: **"Create API Key"**.
  3. "Create API key in new project" select karein.
  4. Ek lambi code line aayegi. Use **COPY** karein (Copy button dabayein).
- **Paste Kahan Karein**: `.env` file mein `GOOGLE_API_KEY=` ke aage.

### 2. LiveKit Keys (The Voice) 🎤
Ye Shell ko bolne aur sunne ki shakti deta hai.
- **Link**: [LiveKit Cloud](https://cloud.livekit.io/)
- **Steps**:
  1. Signup karein (Github/Google se).
  2. New Project banayein (Naam: "Shell").
  3. Left side menu mein **Settings (⚙️ icon)** par click karein.
  4. **KEYS** section mein jayen.
  5. Right side mein **Generate New Key** ya existing key dekhein.
  6. **API Key** Copy karein -> Paste in `.env` (`LIVEKIT_API_KEY=`).
  7. **Secret Key** Copy karein -> Paste in `.env` (`LIVEKIT_API_SECRET=`).
  8. Wapas upar jayen, wahan ek **WebSocket URL** hoga (`wss://...` se shuru). Copy -> Paste (`LIVEKIT_URL=`).

---

## 🟡 SECTION B: Tools (Bohot Kaam Ke)

### 3. Google Search (Internet Access) 🌍
Taaki Shell Google search kar sake.
- **API Key Link**: [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
  1. "Create Credentials" -> "API Key". Copy karein.
  2. Paste in `.env` (`GOOGLE_SEARCH_API_KEY=`).
- **Search Engine ID Link**: [Programmable Search](https://programmablesearchengine.google.com/)
  1. "Add" click karein.
  2. "Search the entire web" select karein.
  3. Create karne ke baad **"Search Engine ID"** (cx) milegi. Copy karein.
  4. Paste in `.env` (`SEARCH_ENGINE_ID=`).

### 4. Weather (Mausam) ⛅
- **Link**: [OpenWeatherMap](https://home.openweathermap.org/api_keys)
- **Steps**: Signup karein -> "API Keys" tab mein jayen -> Key copy karein -> Paste (`OPENWEATHER_API_KEY=`).

### 5. News (Khabrein) 📰
- **Link**: [NewsData.io](https://newsdata.io/api-key)
- **Steps**: Signup karein -> Dashboard par API Key dikhegi -> Copy -> Paste (`NEWS_API_KEY=`).

---

## 🟣 SECTION C: Super Brains (Optional Pro)
Agar aap chahte hain ki Shell **OpenAI, Mistral, Groq** ya dusre optional providers bhi use kare.

### 6. OpenAI (ChatGPT-4o) 🤖
- **Link**: [OpenAI Keys](https://platform.openai.com/api-keys)
- **Steps**: Signup -> "Create new secret key" -> Copy -> Paste (`OPENAI_API_KEY=`).
- *Note: Iske liye shayad card add karna padta hai.*

### 8. Groq (Fast LLM Provider) ⚡
Ye bohot fast hai free mein.
- **Link**: [Groq Console](https://console.groq.com/keys)
- **Steps**: "Create API Key" -> Copy -> Paste (`GROQ_API_KEY=`).

### 9. Sambanova (Llama provider) 🦙
Large hosted model provider.
- **Link**: [Sambanova Cloud](https://cloud.sambanova.ai/)
- **Steps**: Signup -> API Key copy karein -> Paste (`SAMBANOVA_API_KEY=`).

### 10. Mistral AI 🌪️
- **Link**: [Mistral Console](https://console.mistral.ai/api-keys/)
- **Steps**: Create new key -> Copy -> Paste (`MISTRAL_API_KEY=`).

---

## 🔵 SECTION D: Specialized Tools

### 11. HuggingFace (Image Generation) 🎨
Agar aapko AI Images banwanoi hain.
- **Link**: [HuggingFace Tokens](https://huggingface.co/settings/tokens)
- **Steps**: Signup -> "New Token" -> Role: Write -> Copy -> Paste (`HUGGINGFACE_API_KEY=`).

### 12. Alpha Vantage (Stock Market) 📈
Share market prices ke liye.
- **Link**: [Alpha Vantage](https://www.alphavantage.co/support/#api-key)
- **Steps**: "Get Free API Key" -> Form bharein -> Key milegi -> Paste (`ALPHA_VANTAGE_API_KEY=`).

---

# 🎤 PART 4.5: Voice Settings (Shell ki Awaaz)

Shell **30 Gemini voices** support karta hai. Default voice **Aoede**
(female, breezy, natural Hinglish feel). Agar badalni hai:

```env
# .env file mein
VOICE_NAME=Aoede                  # default — koi aur naam daal sakte ho
VOICE_PERSONA=Hinglish            # Hinglish / English / Hindi / Formal / Casual / English-Indian
```

**Popular voices:**
- 🎯 **Aoede** (default) — female, smooth, Hinglish perfect
- 🔥 **Charon** — male, deep, authoritative
- ⚡ **Kore** — female, firm, professional
- 😎 **Puck** — male, upbeat, friendly
- 💫 **Zephyr** — female, bright, energetic

Shell chalane ke baad **runtime pe bhi voice badal sakte ho** — bas bolo:
*"Shell, voice Charon kar do"* ya *"Hindi mein baat karo"*.

Complete list + test:
```bash
venv\Scripts\python.exe -c "from shell_voice import VOICE_NAMES; print('\n'.join(VOICE_NAMES))"
```

---

# 🛡️ PART 4.6: Safety Settings (Optional — Advanced Users Only)

Shell ki **Evolution / Self-Heal / Sentinel** tools LLM se code generate
karke disk pe likhne ki capability rakhti hain. Security ke liye ye
**by default OFF** hain. Enable karni ho to `.env` mein:

```env
# SIRF agar aapko pata hai aap kya kar rahe hain:
SHELL_ALLOW_CODE_WRITE=0        # 1 kar do to create_capability_tool run karega
SHELL_ALLOW_AGENT_PATCH=0       # 1 kar do to agent.py bhi patch ho sakti hai
```

⚠️ **Warning:** Enable karne se pehle apna code `git commit` kar do.
Agar Gemini galat code generate kare to rollback easy rahe.

Har write `.shell_safety_audit.log` mein log hoti hai.

---

# 🎮 PART 5: Launch! (Shubh Aarambh)

Sab kuch set hai! Ab magic dekhein.

## Option A: One-command launch (Recommended)
1. Main folder mein **`Start_ShellAI.bat`** par double click karein.
2. Ek launcher window khulegi. Shell Hub background mein start hoga aur Shell
   Web UI open hogi.
3. Agar start fail ho, launcher khud last `hub.log` aur `ui.log` lines dikhayega.
4. Jab voice ready ho, logs mein is type ki line dikhegi:
   ```
   🎤 Voice selected: Aoede (persona=Hinglish)
   ✅ Realtime TTS used for voice announcement
   ```
   matlab Shell ready hai. Aoede short startup message bolegi, jaise **"Shell OS 1.0.0 online. Created by mdshoebking."**

## Option B: Direct agent only (Voice-only mode)
```bash
venv\Scripts\python.exe agent.py console
```
Bas mic wala voice mode, UI nahi. Hands-free testing ke liye best.

## Option C: Test without mic (Text mode)
```bash
venv\Scripts\python.exe agent.py console --text
```
Text type karo, Aoede voice mein reply sunoge.

Ab mic mein bole: **"Hello Shell!"** 🎤

---

# ❓ Trouble? (Dikkat Aa Rahi Hai?)

**Q: "Python is not recognized" error aa raha hai?**
A: Aapne Python install karte waqt **"Add to PATH"** tick nahi kiya. Python uninstall karke dobara install karein aur tick lagana na bhulein.

**Q: Shell baat nahi kar rahi?**
A: `.env` file check karein. `LIVEKIT` keys aur `GOOGLE_API_KEY` sahi se dali hain ya nahi.

**Q: "Quota Exceeded" error aa raha hai?**
A: Aapki Google key ki limit khatam ho gayi hai. Kisi dusri Gmail ID se nayi key banayein.

**Q: Voice Aoede nahi lag rahi, koi aur hai?**
A: `.env` mein `VOICE_NAME=Aoede` check karein. Log mein `🎤 Voice selected: <naam>` line dhundhein. Agar galat hai to typo check karein — case-insensitive hai lekin spelling right honi chahiye.

**Q: "Tesseract not found" warning?**
A: OCR Gemini Vision pe fallback ho jata hai (slower but works). Ya `winget install UB-Mannheim.TesseractOCR` chalao Windows mein, ya `.env` mein `TESSERACT_CMD=C:\path\to\tesseract.exe` set karo.

**Q: "EVOLUTION BLOCKED" ya "HOTPATCH BLOCKED" messages?**
A: Ye safety feature hai — by design OFF. Enable karna ho to `SHELL_ALLOW_CODE_WRITE=1` kar do `.env` mein. Par pehle padho upar ka PART 4.6.

**Q: WhatsApp send nahi ho raha?**
A: Desktop WhatsApp app use kar rahe ho to ensure `send_whatsapp_message` ke time WhatsApp window khuli ho. Ya Selenium backend try karo: `link_whatsapp_device()` se QR scan karke web session activate karo.

**Q: "AGENT TOOLS LOADED (300+)" kam dikha raha?**
A: Sab optional modules available nahi hain shayad. Logs mein `DEBUG` mode enable karo (`LOG_LEVEL=DEBUG` in `.env`) — dikh jayega kaun sa import fail hua. Optional modules missing hone se core voice kaam karti rahegi.

**Enjoy Your New Voice Computer!** 🦅
*Built with ❤️ by Md Shoeb King*

---

# PART 6: Smart Email Automation (Company Ko Auto Mail)

Agar aap chahte ho Shell bole jaane par company ko professional email khud bheje, to ye setup karein:

1. `.env` file me SMTP details add karein:
   - `SHELL_SMTP_SERVER=smtp.gmail.com`
   - `SHELL_SMTP_PORT=587`
   - `SHELL_SMTP_USE_SSL=false`
   - `SHELL_GMAIL_WEB_PROFILE_DIR=~/.shell_gmail_chrome` (web fallback login session)
   - `SHELL_EMAIL_WEB_FALLBACK=true` (SMTP fail hone par automatic web-send fallback)
   - `SHELL_SENDER_EMAIL=your_email@gmail.com`
   - `SHELL_SENDER_PASSWORD=your_app_password`

2. Professional signature ke liye optional profile set karein:
   - `SHELL_SENDER_NAME=`
   - `SHELL_SENDER_ROLE=`
   - `SHELL_SENDER_COMPANY=`
   - `SHELL_SENDER_PHONE=`
   - `SHELL_SENDER_WEBSITE=`

3. Company email auto-find ke liye required:
   - `GOOGLE_SEARCH_API_KEY`
   - `SEARCH_ENGINE_ID`

4. Voice examples:
   - "Shell, XYZ company ko partnership ke liye mail karo."
   - "Shell, ABC ko professional business inquiry bhejo."

Note: Shell sirf public web contact emails dhoondhne ki koshish karega. Agar email na mile to recipient manually dena padega.
If SMTP app password issue aaye, Shell Gmail Web mode me browser kholkar compose + send kar sakta hai.
