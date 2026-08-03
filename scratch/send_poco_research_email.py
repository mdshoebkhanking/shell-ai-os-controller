import sys
import os
import asyncio

sys.path.insert(0, os.getcwd())
from shell_email_tool import send_email_tool

async def main():
    recipient = "zestking300@gmail.com"
    subject = "POCO X3 & X3 Pro - Deep Research Report (Hinglish)"
    
    # 1. Plain Text Version
    body = """POCO X3 & X3 Pro - Deep Research Report 📱
--------------------------------------------------

Hey Md Shoeb King! 

Aapke request ke mutabik, maine POCO X3 aur POCO X3 Pro par deep internet research, Reddit discussions, aur tech forums se details nikal kar yeh comprehensive report compile ki hai. 

Neeche dono devices ki details aur common issues (jaise Motherboard Dead issue) ke baare mein complete analysis di gayi hai:

1. Overview & Specifications Comparison
--------------------------------------------------
* POCO X3 (Codename: surya/karna):
  - Processor: Qualcomm Snapdragon 732G (8nm)
  - Display: 6.67" IPS LCD, 120Hz, HDR10
  - Rear Camera: 64 MP (Main) + 13 MP (Ultrawide) + 2 MP (Macro) + 2 MP (Depth)
  - Front Camera: 20 MP
  - Battery: 5160 mAh (NFC version) / 6000 mAh (Indian version), 33W Fast Charging
  - Build: Plastic back, Glass front (Gorilla Glass 5)

* POCO X3 Pro (Codename: vayu/bhima):
  - Processor: Qualcomm Snapdragon 860 (7nm) - Flagship Level Performance
  - Display: 6.67" IPS LCD, 120Hz, HDR10
  - Rear Camera: 48 MP (Main) + 8 MP (Ultrawide) + 2 MP (Macro) + 2 MP (Depth)
  - Front Camera: 20 MP
  - Battery: 5160 mAh, 33W Fast Charging
  - Build: Plastic back, Glass front (Gorilla Glass 6 - Better Scratch/Drop resistance)

2. Performance: Snapdragon 732G vs Snapdragon 860
--------------------------------------------------
* POCO X3 (732G): Mid-range daily use, social media, aur light/medium gaming (like BGMI at Balanced/Ultra) ke liye standard processor hai. Performance smooth hai par heavy multitasking me thoda lag karta hai.
* POCO X3 Pro (860): Yeh processor Snapdragon 855+ ka rebranded version hai. Gaming performance next level hai (BGMI at Extreme/90FPS with config/gfx, heavy Emulator gaming). Runs very smooth but generates more heat.

3. Motherboard Failure & Deadboot Issue (CRITICAL INFO 🚨)
--------------------------------------------------
* Sabse bada concern POCO X3 Pro (aur kuch Indian POCO X3 models) ke sath hardware-level failure ka raha hai.
* Root Cause: Xiaomi ne assembly ke dauran CPU aur RAM chip ke neeche "low-grade solder paste" use kiya tha. Dynamic thermal cycles (phone ka bar-bar garam aur thanda hona, gaming ke dauran heavy heating) ki wajah se yeh micro-soldering joints crack ho jaate hain.
* Symptoms: Phone achanak switch off ho jata hai, dead ho jata hai (refuses to charge/boot), ya screen par grey stripes aa kar crash ho jata hai.
* Status in 2026: Official motherboards ab milna bohot mushkil hain aur device ab out-of-warranty hai. 
* Solution: Local experienced repair shops "CPU Reballing" (CPU ko chip se utaar kar fir se nayi acchi solder paste ke sath lagana) karke isse thik kar dete hain ($25-$40 ya Rs.2000-Rs.3500 range me). Par yeh permanent fix nahi hota aur iski long-term durability guarantee nahi hoti.

4. Custom ROMs & Modding Support (Active in 2026 🌐)
--------------------------------------------------
* Xiaomi ne in devices ke liye official software support (MIUI/HyperOS) end kar diya hai.
* Par community support abhi bhi bohot active hai! Developer communities (XDA Developers) in devices par Android 15 aur early Android 16 custom ROMs chala rahi hain.
* Popular ROMs: LineageOS, crDroid, Project Elixir, aur ArrowOS daily driver ke taur par bohot popular hain. Inse user interface bilkul clean Stock Android ho jata hai aur safety updates bhi milte hain.
* SafeNet/Banking Apps: Banking apps chalane ke liye Play Integrity patches require hote hain, jo custom ROMs build-in provide karti hain.

5. Final Verdict (2026 Relevance)
--------------------------------------------------
* Agar aapke paas device chal raha hai: Isko custom ROM ke sath use karte rahein, par important data ka backup zaroor banayein (motherboard dead issue achanak aata hai).
* Agar phone dead ho gaya hai: Motherboard change karwana ya high-cost board repair karwana 2026 me bilkul value-for-money nahi hai. Naye 5G devices bohot saste aur powerful mil rahe hain.

---
This report was generated and emailed automatically by Shell AI.
"""

    # 2. HTML Version (Stunning Glassmorphism / Cyberpunk Dark Theme)
    html_body = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>POCO X3 & X3 Pro Research Report</title>
<style>
  body {
    background-color: #0c0f16;
    color: #e2e8f0;
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    margin: 0;
    padding: 20px;
    line-height: 1.6;
  }
  .container {
    max-width: 700px;
    margin: 0 auto;
    background: linear-gradient(135deg, #121622 0%, #182035 100%);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 20px;
    padding: 30px;
    box-shadow: 0 10px 40px rgba(0,0,0,0.6);
  }
  .header {
    border-bottom: 2px solid #f39c12;
    padding-bottom: 20px;
    margin-bottom: 25px;
    text-align: center;
  }
  .header h1 {
    color: #ffc107;
    margin: 0 0 10px 0;
    font-size: 28px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1.5px;
  }
  .header p {
    color: #a0aec0;
    margin: 0;
    font-size: 14px;
  }
  .badge {
    background-color: #f39c12;
    color: #121212;
    padding: 4px 10px;
    border-radius: 20px;
    font-size: 11px;
    font-weight: bold;
    display: inline-block;
    margin-top: 5px;
  }
  .section-title {
    color: #ffc107;
    font-size: 20px;
    border-left: 4px solid #f39c12;
    padding-left: 12px;
    margin-top: 30px;
    margin-bottom: 15px;
    font-weight: 600;
  }
  .card {
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.05);
    border-radius: 12px;
    padding: 18px;
    margin-bottom: 18px;
  }
  .card-warning {
    background: rgba(231, 76, 60, 0.05);
    border: 1px solid rgba(231, 76, 60, 0.25);
    border-radius: 12px;
    padding: 18px;
    margin-bottom: 18px;
  }
  .card-warning h4 {
    color: #e74c3c;
    margin: 0 0 8px 0;
    font-size: 16px;
    display: flex;
    align-items: center;
  }
  .specs-table {
    width: 100%;
    border-collapse: collapse;
    margin-top: 10px;
    margin-bottom: 20px;
    font-size: 14px;
  }
  .specs-table th {
    background-color: rgba(243, 156, 18, 0.15);
    color: #ffc107;
    text-align: left;
    padding: 10px;
    border: 1px solid rgba(255, 255, 255, 0.1);
  }
  .specs-table td {
    padding: 10px;
    border: 1px solid rgba(255, 255, 255, 0.08);
  }
  .specs-table tr:nth-child(even) {
    background-color: rgba(255, 255, 255, 0.01);
  }
  ul {
    padding-left: 20px;
    margin: 10px 0;
  }
  li {
    margin-bottom: 8px;
  }
  .footer {
    text-align: center;
    margin-top: 40px;
    border-top: 1px solid rgba(255, 255, 255, 0.08);
    padding-top: 20px;
    font-size: 12px;
    color: #718096;
  }
  .highlight {
    color: #00d2ff;
    font-weight: bold;
  }
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>POCO X3 & X3 Pro</h1>
    <p>Deep Research & Analysis Report</p>
    <span class="badge">SYSTEM REPORT</span>
  </div>

  <p>Hey Md Shoeb King! Aapke request ke mutabik, maine POCO X3 aur POCO X3 Pro par deep internet research aur tech forum discussions se details compile ki hain. Yeh report dono devices ke hardware, performance, issues, aur 2026 me unki status ke baare me deep insights deti hai.</p>

  <div class="section-title">1. Specifications Comparison Table</div>
  <table class="specs-table">
    <thead>
      <tr>
        <th>Specification</th>
        <th>POCO X3 (surya/karna)</th>
        <th>POCO X3 Pro (vayu/bhima)</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td><strong>Processor</strong></td>
        <td>Snapdragon 732G (8nm)</td>
        <td><span class="highlight">Snapdragon 860 (7nm)</span></td>
      </tr>
      <tr>
        <td><strong>Display</strong></td>
        <td>6.67" IPS LCD, 120Hz, Gorilla Glass 5</td>
        <td>6.67" IPS LCD, 120Hz, <span class="highlight">Gorilla Glass 6</span></td>
      </tr>
      <tr>
        <td><strong>Rear Camera</strong></td>
        <td><span class="highlight">64 MP Quad Camera</span></td>
        <td>48 MP Quad Camera</td>
      </tr>
      <tr>
        <td><strong>Battery & Charge</strong></td>
        <td>5160 mAh / 6000 mAh, 33W Fast</td>
        <td>5160 mAh, 33W Fast Charging</td>
      </tr>
      <tr>
        <td><strong>Storage Type</strong></td>
        <td>UFS 2.1</td>
        <td><span class="highlight">UFS 3.1 (Fast Read/Write)</span></td>
      </tr>
    </tbody>
  </table>

  <div class="section-title">2. Performance Analysis: 732G vs 860</div>
  <div class="card">
    <ul>
      <li><strong>POCO X3 (Snapdragon 732G):</strong> Yeh display 120Hz refresh rate par standard operations aur daily tasks ke liye smooth hai. Moderate gaming (jaise BGMI ya Free Fire medium settings par) easily handle karta hai, par processing power limited hai.</li>
      <li><strong>POCO X3 Pro (Snapdragon 860):</strong> Snapdragon 855+ ka optimized version hone ke karan iski raw performance gaming me beast hai. UFS 3.1 storage apps loads fast aur BGMI high graphics me support karta hai, par heavy gaming pe system ka temperature jaldi rise hota hai.</li>
    </ul>
  </div>

  <div class="section-title">3. Critical Issue: Motherboard Failure & Sudden Death</div>
  <div class="card-warning">
    <h4>🚨 Motherboard Deadboot Warning (Most Common in X3 Pro)</h4>
    <p>POCO X3 Pro (aur Indian variants) me major hardware design defect ke karan motherboard sudden failure face karta hai:</p>
    <ul>
      <li><strong>Root Cause:</strong> Factory soldering me lead-free low-grade solder paste use kiya gaya tha. Over time, heavy processing heating se soldering balls crack ho jaate hain aur CPU ka contact board se toot jata hai.</li>
      <li><strong>Symptoms:</strong> Screen par sudden lines aana, white/grey screen freeze ho jana, ya bina kisi reason ke device complete switch off (dead) ho jana.</li>
      <li><strong>Solution in 2026:</strong> Local market me skilled technicians <strong>CPU Reballing</strong> karke ise temporarily thik karte hain (Rs.2000 - Rs.3500 range). Lekin motherboard replacement ab design age ke karan not recommended aur out-of-stock hai.</li>
    </ul>
  </div>

  <div class="section-title">4. Software & Custom ROMs (2026 Status)</h2>
  <div class="card">
    <p>Xiaomi ne official support band kar diya hai, par custom ROM community me dono phones bohot popular hain:</p>
    <ul>
      <li><strong>LineageOS, crDroid, Project Elixir:</strong> In custom ROMs ki madad se aap stable <strong>Android 15</strong> aur early <strong>Android 16</strong> chala sakte hain.</li>
      <li><strong>SafetyNet / Play Integrity:</strong> Google ke naye security updates ke baad, custom ROMs ke developers safety patches regularly update karte hain taaki Banking aur UPI apps run karte rahein.</li>
    </ul>
  </div>

  <div class="section-title">5. Final Verdict / Recommendation</div>
  <div class="card">
    <p>Agar aapka phone sahi chal raha hai, to iska hardware smooth custom ROM par active rakhein par data ka regular cloud backup lete rahein. Agar hardware dead ho chuka hai, to recovery ke alawa motherboard changes pe paise kharch karna 2026 me waste of money hai.</p>
  </div>

  <div class="footer">
    <p>Report automatically compiled and delivered by <strong>Shell AI OS Controller</strong>.</p>
    <p>Configured SMTP Server: smtp.gmail.com</p>
  </div>
</div>
</body>
</html>
"""

    print(f"Sending email to {recipient}...")
    res = await send_email_tool(
        recipient=recipient,
        subject=subject,
        body=body,
        html_body=html_body
    )
    print("Execution Result:")
    print(res)

if __name__ == "__main__":
    asyncio.run(main())
