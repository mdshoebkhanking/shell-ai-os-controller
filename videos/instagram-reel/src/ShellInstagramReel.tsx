import type { CSSProperties, ReactNode } from "react";
import { Audio } from "@remotion/media";
import {
  AbsoluteFill,
  Easing,
  Img,
  Sequence,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

const c = {
  bg: "#05070B",
  screen: "#0B1018",
  panel: "#101722",
  text: "#F8FAFC",
  muted: "#A7B3C8",
  dim: "#65738A",
  cyan: "#40D9F5",
  green: "#64E6AE",
  amber: "#FBBF24",
  pink: "#F472B6",
  red: "#FB7185",
  line: "#263245",
};

const font =
  'Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif';
const mono = '"SFMono-Regular", Consolas, "Liberation Mono", monospace';
const FPS = 30;
const SHOT = 90;

const clamp = (v: number, min = 0, max = 1) => Math.min(max, Math.max(min, v));
const ease = (frame: number, start: number, duration: number) =>
  interpolate(frame, [start, start + duration], [0, 1], {
    easing: Easing.bezier(0.16, 1, 0.3, 1),
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

const out = (frame: number, duration: number) =>
  interpolate(frame, [duration - 12, duration], [1, 0], {
    easing: Easing.in(Easing.cubic),
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

const typeSlice = (text: string, frame: number, start: number, duration: number) => {
  const progress = ease(frame, start, duration);
  return text.slice(0, Math.floor(text.length * progress));
};

const ShotWrap = ({
  label,
  caption,
  children,
}: {
  label: string;
  caption: string;
  children: ReactNode;
}) => {
  const frame = useCurrentFrame();
  const enter = ease(frame, 0, 14);
  const opacity = out(frame, SHOT);
  const y = interpolate(enter, [0, 1], [18, 0]);

  return (
    <AbsoluteFill
      style={{
        opacity,
        transform: `translateY(${y}px)`,
        padding: "86px 54px 92px",
      }}
    >
      <div
        style={{
          position: "absolute",
          top: 40,
          left: 54,
          right: 54,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          color: c.dim,
          fontFamily: font,
          fontSize: 17,
          fontWeight: 850,
          letterSpacing: 1.7,
          textTransform: "uppercase",
        }}
      >
        <span>Shell AI Live Workflow</span>
        <span style={{ color: c.green }}>Running</span>
      </div>
      <div style={{ ...smallLabel, marginBottom: 16 }}>{label}</div>
      {children}
      <div style={captionStyle}>{caption}</div>
    </AbsoluteFill>
  );
};

const Stage = ({ children }: { children: ReactNode }) => {
  const frame = useCurrentFrame();
  const scan = (frame * 3) % 1920;
  return (
    <AbsoluteFill
      style={{
        backgroundColor: c.bg,
        color: c.text,
        fontFamily: font,
        overflow: "hidden",
      }}
    >
      <AbsoluteFill
        style={{
          background:
            "radial-gradient(circle at 25% 8%, rgba(64,217,245,0.22), transparent 31%), radial-gradient(circle at 92% 80%, rgba(244,114,182,0.16), transparent 33%), linear-gradient(170deg, #05070B, #0A0D14 55%, #130B13)",
        }}
      />
      <AbsoluteFill
        style={{
          opacity: 0.25,
          backgroundImage:
            "linear-gradient(rgba(255,255,255,0.045) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.04) 1px, transparent 1px)",
          backgroundSize: "58px 58px",
        }}
      />
      <div
        style={{
          position: "absolute",
          top: scan - 180,
          left: 0,
          right: 0,
          height: 180,
          background: "linear-gradient(180deg, transparent, rgba(64,217,245,0.11), transparent)",
        }}
      />
      {children}
      <Progress />
      <AudioSuite />
    </AbsoluteFill>
  );
};

const AudioSuite = () => {
  const { durationInFrames, fps } = useVideoConfig();
  const sfxStarts = Array.from({ length: 20 }, (_, i) => i * SHOT);

  return (
    <>
      <Audio
        src={staticFile("audio/liam-shell-voiceover.mp3")}
        trimAfter={Math.floor(57.7 * fps)}
        volume={(f) =>
          Math.min(
            interpolate(f, [0, fps], [0, 0.94], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            }),
            interpolate(f, [durationInFrames - 3 * fps, durationInFrames - fps], [0.94, 0], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            }),
          )
        }
      />
      <Audio src={staticFile("audio/os-ambient-bed.wav")} loop volume={0.22} />
      <Timed from={0} file="boot-chime.wav" volume={0.65} />
      {sfxStarts.slice(1).map((from) => (
        <Timed key={`whoosh-${from}`} from={from - 3} file="data-whoosh.wav" volume={0.30} />
      ))}
      {[105, 198, 292, 470, 642, 735, 1005, 1290, 1510].map((from) => (
        <Timed key={`typing-${from}`} from={from} file="keyboard-burst.wav" volume={0.22} />
      ))}
      {[80, 230, 410, 592, 845, 925, 1135, 1412, 1604].map((from) => (
        <Timed key={`click-${from}`} from={from} file="ui-click.wav" volume={0.22} />
      ))}
      {[350, 700, 1070, 1450, 1720].map((from) => (
        <Timed key={`ok-${from}`} from={from} file="confirm-pulse.wav" volume={0.25} />
      ))}
      {[540, 1180].map((from) => (
        <Timed key={`scan-${from}`} from={from} file="data-scan.wav" volume={0.22} />
      ))}
    </>
  );
};

const Timed = ({ from, file, volume }: { from: number; file: string; volume: number }) => (
  <Sequence from={from}>
    <Audio src={staticFile(`audio/${file}`)} volume={volume} />
  </Sequence>
);

const Progress = () => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  return (
    <div
      style={{
        position: "absolute",
        left: 54,
        right: 54,
        bottom: 44,
        height: 6,
        borderRadius: 999,
        background: "rgba(255,255,255,0.12)",
        overflow: "hidden",
      }}
    >
      <div
        style={{
          width: `${clamp(frame / (durationInFrames - 1)) * 100}%`,
          height: "100%",
          background: `linear-gradient(90deg, ${c.cyan}, ${c.green}, ${c.amber}, ${c.pink})`,
        }}
      />
    </div>
  );
};

const smallLabel: CSSProperties = {
  color: c.muted,
  fontFamily: font,
  fontSize: 22,
  fontWeight: 900,
  letterSpacing: 2.2,
  textTransform: "uppercase",
};

const captionStyle: CSSProperties = {
  position: "absolute",
  left: 54,
  right: 54,
  bottom: 72,
  minHeight: 72,
  borderRadius: 24,
  border: "1px solid rgba(255,255,255,0.13)",
  background: "rgba(5,7,11,0.78)",
  color: c.text,
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  padding: "14px 22px",
  textAlign: "center",
  fontSize: 27,
  fontWeight: 900,
  lineHeight: 1.12,
};

const Screen = ({ children, title = "Shell Desktop" }: { children: ReactNode; title?: string }) => (
  <div
    style={{
      height: 1390,
      borderRadius: 38,
      border: "1px solid rgba(255,255,255,0.16)",
      background: "rgba(8,12,18,0.88)",
      boxShadow: "0 34px 120px rgba(0,0,0,0.42)",
      overflow: "hidden",
    }}
  >
    <div
      style={{
        height: 54,
        display: "flex",
        alignItems: "center",
        gap: 10,
        paddingLeft: 22,
        borderBottom: "1px solid rgba(255,255,255,0.08)",
        background: "rgba(9,13,20,0.95)",
      }}
    >
      {[c.red, c.amber, c.green].map((dot) => (
        <span key={dot} style={{ width: 13, height: 13, borderRadius: 99, background: dot }} />
      ))}
      <span style={{ marginLeft: 14, color: c.muted, fontSize: 18, fontWeight: 800 }}>
        {title}
      </span>
    </div>
    <div style={{ position: "relative", height: 1336 }}>{children}</div>
  </div>
);

const Cursor = ({
  from,
  to,
  start = 12,
  duration = 48,
  clickAt,
}: {
  from: [number, number];
  to: [number, number];
  start?: number;
  duration?: number;
  clickAt?: number;
}) => {
  const frame = useCurrentFrame();
  const p = ease(frame, start, duration);
  const x = interpolate(p, [0, 1], [from[0], to[0]]);
  const y = interpolate(p, [0, 1], [from[1], to[1]]);
  const click = clickAt ? ease(frame, clickAt, 5) - ease(frame, clickAt + 8, 5) : 0;
  return (
    <div
      style={{
        position: "absolute",
        left: x,
        top: y,
        width: 0,
        height: 0,
        zIndex: 20,
      }}
    >
      <div
        style={{
          width: 30,
          height: 30,
          transform: `scale(${1 - click * 0.18}) rotate(-18deg)`,
          clipPath: "polygon(0 0, 0 28px, 8px 20px, 14px 34px, 21px 31px, 15px 17px, 29px 17px)",
          background: "#FFFFFF",
          boxShadow: `0 0 ${24 + click * 50}px rgba(64,217,245,0.7)`,
        }}
      />
      {click > 0 ? (
        <div
          style={{
            position: "absolute",
            left: -18,
            top: -18,
            width: 70,
            height: 70,
            borderRadius: 999,
            border: `2px solid ${c.cyan}`,
            opacity: click,
            transform: `scale(${1 + click * 0.5})`,
          }}
        />
      ) : null}
    </div>
  );
};

const ShellChat = ({
  prompt,
  response,
  typing = true,
}: {
  prompt: string;
  response: string;
  typing?: boolean;
}) => {
  const frame = useCurrentFrame();
  const shownPrompt = typing ? typeSlice(prompt, frame, 8, 44) : prompt;
  const shownResponse = typeSlice(response, frame, 44, 34);

  return (
    <div style={{ position: "absolute", inset: 34, display: "flex", flexDirection: "column", gap: 18 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
        <Img src={staticFile("brand/shell-official-logo.png")} style={{ width: 66, height: 66 }} />
        <div>
          <div style={{ color: c.text, fontSize: 31, fontWeight: 950 }}>Shell</div>
          <div style={{ color: c.green, fontSize: 18, fontWeight: 850 }}>listening + tool routing</div>
        </div>
      </div>
      <Bubble who="You" text={shownPrompt} tone={c.cyan} />
      <Bubble who="Shell" text={shownResponse} tone={c.green} />
      <div style={{ marginTop: "auto", borderTop: `1px solid ${c.line}`, paddingTop: 18 }}>
        <div style={{ color: c.dim, fontSize: 20, fontWeight: 800 }}>tools: mouse, keyboard, browser, files, terminal</div>
      </div>
    </div>
  );
};

const Bubble = ({ who, text, tone }: { who: string; text: string; tone: string }) => (
  <div
    style={{
      border: `1px solid ${tone}55`,
      background: `${tone}18`,
      borderRadius: 24,
      padding: "20px 22px",
    }}
  >
    <div style={{ color: tone, fontSize: 18, fontWeight: 900, letterSpacing: 1.6, marginBottom: 8 }}>
      {who}
    </div>
    <div style={{ color: c.text, fontSize: 30, fontWeight: 780, lineHeight: 1.16 }}>{text}</div>
  </div>
);

const Browser = ({
  url,
  children,
}: {
  url: string;
  children: ReactNode;
}) => (
  <div style={{ position: "absolute", inset: 28, borderRadius: 28, overflow: "hidden", border: `1px solid ${c.line}`, background: "#FAFBFC" }}>
    <div style={{ height: 58, background: "#E8EDF3", display: "flex", alignItems: "center", gap: 12, padding: "0 18px" }}>
      <div style={{ display: "flex", gap: 8 }}>{[c.red, c.amber, c.green].map((d) => <span key={d} style={{ width: 12, height: 12, borderRadius: 99, background: d }} />)}</div>
      <div style={{ flex: 1, height: 32, borderRadius: 999, background: "#FFFFFF", color: "#334155", fontSize: 17, fontWeight: 800, display: "flex", alignItems: "center", paddingLeft: 18 }}>{url}</div>
    </div>
    <div style={{ height: "calc(100% - 58px)", color: "#111827" }}>{children}</div>
  </div>
);

const LandingPage = ({ progress = 1 }: { progress?: number }) => (
  <div style={{ height: "100%", background: "#F8FAFC", padding: 28 }}>
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 36 }}>
      <div style={{ fontSize: 26, fontWeight: 950 }}>Nova Studio</div>
      <div style={{ display: "flex", gap: 18, color: "#64748B", fontSize: 16, fontWeight: 800 }}>
        <span>Work</span><span>Pricing</span><span>Contact</span>
      </div>
    </div>
    <div style={{ opacity: ease(progress * 60, 0, 20) }}>
      <div style={{ fontSize: 58, fontWeight: 950, lineHeight: 0.96, maxWidth: 650 }}>
        Launch your AI product faster.
      </div>
      <p style={{ color: "#64748B", fontSize: 23, lineHeight: 1.25, maxWidth: 680, marginTop: 18 }}>
        A clean landing page generated, previewed, and refined from one Shell request.
      </p>
    </div>
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20, marginTop: 36 }}>
      {["Responsive design", "Contact form", "Hero section", "SEO-ready copy"].map((item, i) => (
        <div key={item} style={{ opacity: progress > i * 0.2 ? 1 : 0.18, borderRadius: 22, background: "#FFFFFF", padding: 22, boxShadow: "0 16px 40px rgba(15,23,42,0.08)", fontSize: 21, fontWeight: 850 }}>
          {item}
        </div>
      ))}
    </div>
  </div>
);

const CodePanel = ({ lines }: { lines: string[] }) => {
  const frame = useCurrentFrame();
  return (
    <div style={{ position: "absolute", inset: 30, borderRadius: 28, background: "#070B12", padding: 26, border: `1px solid ${c.line}` }}>
      {lines.map((line, i) => (
        <div key={`${line}-${i}`} style={{ fontFamily: mono, fontSize: 23, lineHeight: 1.5, color: i % 3 === 0 ? c.green : i % 3 === 1 ? c.cyan : c.muted, opacity: i === 0 ? 1 : ease(frame, Math.max(0, i * 4 - 4), 12) }}>
          {line}
        </div>
      ))}
    </div>
  );
};

const Terminal = ({ commands }: { commands: string[] }) => {
  const frame = useCurrentFrame();
  return (
    <div style={{ position: "absolute", inset: 34, borderRadius: 28, background: "#030712", padding: 28, border: `1px solid ${c.line}` }}>
      {commands.map((cmd, i) => (
        <div key={cmd} style={{ fontFamily: mono, fontSize: 24, lineHeight: 1.55, color: cmd.includes("PASS") || cmd.includes("ready") ? c.green : c.text, opacity: i === 0 ? 1 : ease(frame, Math.max(0, i * 10 - 6), 10) }}>
          <span style={{ color: c.cyan }}>$ </span>{cmd}
        </div>
      ))}
    </div>
  );
};

const CenterHero = ({ title, subtitle }: { title: string; subtitle: string }) => (
  <Screen title="Shell AI OS">
    <div style={{ position: "absolute", inset: 54, display: "grid", placeItems: "center", textAlign: "center" }}>
      <div>
        <Img src={staticFile("brand/shell-official-logo.png")} style={{ width: 190, height: 190, marginBottom: 34 }} />
        <div style={{ fontSize: 72, fontWeight: 950, lineHeight: 0.94 }}>{title}</div>
        <div style={{ color: c.muted, fontSize: 30, fontWeight: 780, lineHeight: 1.18, marginTop: 22 }}>{subtitle}</div>
      </div>
    </div>
  </Screen>
);

const EcosystemGrid = ({ items }: { items: string[] }) => {
  const frame = useCurrentFrame();
  return (
    <div style={{ position: "absolute", inset: 46, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
      {items.map((item, i) => (
        <div
          key={item}
          style={{
            opacity: i === 0 ? 1 : ease(frame, Math.max(0, i * 5 - 4), 14),
            borderRadius: 24,
            border: `1px solid ${i % 2 ? c.green : c.cyan}55`,
            background: `${i % 2 ? c.green : c.cyan}18`,
            display: "grid",
            placeItems: "center",
            textAlign: "center",
            color: c.text,
            fontSize: 34,
            fontWeight: 950,
            lineHeight: 1.04,
            padding: 20,
          }}
        >
          {item}
        </div>
      ))}
    </div>
  );
};

const splitShots = [
  () => (
    <ShotWrap label="Future is being built" caption="Future abhi isi waqt ban raha hai.">
      <CenterHero title="The future is live." subtitle="Shell AI OS Controller starts the workflow." />
    </ShotWrap>
  ),
  () => (
    <ShotWrap label="Build now" caption="Shell prompt leti hai aur kaam start karti hai.">
      <Screen><ShellChat prompt="Shell, build a website and control the workflow." response="Starting now: browser, typing, files, preview, checks." /></Screen>
      <Cursor from={[750, 960]} to={[585, 1065]} clickAt={70} />
    </ShotWrap>
  ),
  () => (
    <ShotWrap label="Control technology" caption="Jo technology control karega, wahi workflow define karega.">
      <Screen><ShellChat prompt="Open browser and begin automation." response="Mouse control active. Opening browser..." typing={false} /></Screen>
      <Cursor from={[170, 980]} to={[725, 370]} start={6} duration={55} clickAt={66} />
    </ShotWrap>
  ),
  () => (
    <ShotWrap label="Keyboard automation" caption="Shell khud type kar rahi hai, user nahi.">
      <Screen><ShellChat prompt="Create a modern landing page with sections, buttons and responsive CSS." response="Typing prompt, preparing files and preview route..." /></Screen>
      <Cursor from={[760, 1030]} to={[250, 1010]} start={4} duration={30} clickAt={38} />
    </ShotWrap>
  ),
  () => (
    <ShotWrap label="Shell AI OS" caption="Pesh hai Shell AI OS: automation ka powerhouse.">
      <CenterHero title="Shell AI OS" subtitle="Automation ka next-generation powerhouse." />
    </ShotWrap>
  ),
  () => (
    <ShotWrap label="Automation powerhouse" caption="Plan, tools, browser, files - sab ek flow me.">
      <Screen><Terminal commands={["plan.create workflow", "tool: browser.open", "tool: keyboard.type", "tool: file.write", "tool: preview.run", "status: automation ready"]} /></Screen>
    </ShotWrap>
  ),
  () => (
    <ShotWrap label="Workflow control" caption="Apne workflow ko Shell se control karo.">
      <Screen>
        <Browser url="http://localhost:3000"><div style={{ height: "100%", display: "grid", placeItems: "center", background: "#0F172A", color: "#E2E8F0", fontSize: 42, fontWeight: 950 }}>Opening local preview...</div></Browser>
      </Screen>
      <Cursor from={[320, 280]} to={[630, 205]} start={14} duration={44} clickAt={64} />
    </ShotWrap>
  ),
  () => (
    <ShotWrap label="AI intelligence build" caption="AI intelligence build: HTML aur CSS generate.">
      <Screen><CodePanel lines={["<!doctype html>", "<section class=\"hero\">", "  <h1>Launch your AI product faster</h1>", "  <button>Book a demo</button>", "</section>", ".hero { display: grid; }"]} /></Screen>
    </ShotWrap>
  ),
  () => (
    <ShotWrap label="Automate everything" caption="Preview, test, screenshot, terminal - everything automated.">
      <Screen><Terminal commands={["npm run preview", "localhost:3000 ready", "capture screenshot", "run UI probe", "UI probe PASS"]} /></Screen>
    </ShotWrap>
  ),
  () => (
    <ShotWrap label="For creators" caption="Creators ke liye: website instantly preview hoti hai.">
      <Screen><Browser url="http://localhost:3000"><LandingPage progress={1} /></Browser></Screen>
    </ShotWrap>
  ),
  () => (
    <ShotWrap label="For developers" caption="Developers ke liye: commands, files, checks.">
      <Screen><CodePanel lines={["created: index.html", "created: styles.css", "saved: shell_projects/site", "test: responsive layout", "lint: clean", "status: ready"]} /></Screen>
    </ShotWrap>
  ),
  () => (
    <ShotWrap label="For innovators" caption="Innovators aur future leaders ke liye automation stack.">
      <Screen><EcosystemGrid items={["Creators", "Developers", "Innovators", "Future leaders"]} /></Screen>
    </ShotWrap>
  ),
  () => (
    <ShotWrap label="Not just software" caption="Yeh sirf software nahi hai.">
      <Screen title="AI Ecosystem"><EcosystemGrid items={["Local UI", "Runtime Hub", "Tool Gateway", "Memory + Logs"]} /></Screen>
    </ShotWrap>
  ),
  () => (
    <ShotWrap label="Complete ecosystem" caption="Yeh complete AI ecosystem hai.">
      <Screen title="Connected system"><EcosystemGrid items={["Desktop", "Browser", "Files", "Automation"]} /></Screen>
    </ShotWrap>
  ),
  () => (
    <ShotWrap label="Chat, voice, tools" caption="Chat, voice, tools - ek hi intelligent platform.">
      <Screen><EcosystemGrid items={["Chat", "Voice", "Tools", "Agents"]} /></Screen>
    </ShotWrap>
  ),
  () => (
    <ShotWrap label="Agents and plugins" caption="Agents, plugins, workflows - sab connected.">
      <Screen>
        <Img src={staticFile("screenshots/tools-catalog.png")} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
      </Screen>
      <Cursor from={[820, 1140]} to={[470, 700]} start={10} duration={58} clickAt={70} />
    </ShotWrap>
  ),
  () => (
    <ShotWrap label="Human control" caption="Human control ke saath real AI automation.">
      <Screen>
        <div style={{ position: "absolute", inset: 44, display: "grid", placeItems: "center" }}>
          <div style={{ width: 760, borderRadius: 34, border: `1px solid ${c.amber}77`, background: "rgba(16,23,34,0.94)", padding: 34 }}>
            <div style={{ color: c.amber, fontSize: 22, fontWeight: 950, letterSpacing: 2, textTransform: "uppercase" }}>Approval required</div>
            <div style={{ fontSize: 44, fontWeight: 950, lineHeight: 1.05, marginTop: 12 }}>Write generated files?</div>
            <div style={{ color: c.muted, fontSize: 25, lineHeight: 1.2, marginTop: 14 }}>Shell asks before risky actions.</div>
            <div style={{ display: "flex", gap: 14, marginTop: 28 }}>
              <div style={{ flex: 1, borderRadius: 18, background: `${c.green}33`, color: c.green, padding: 18, textAlign: "center", fontSize: 25, fontWeight: 950 }}>Approve</div>
              <div style={{ flex: 1, borderRadius: 18, background: "rgba(255,255,255,0.08)", color: c.muted, padding: 18, textAlign: "center", fontSize: 25, fontWeight: 850 }}>Cancel</div>
            </div>
          </div>
        </div>
      </Screen>
      <Cursor from={[730, 980]} to={[330, 915]} start={16} duration={42} clickAt={65} />
    </ShotWrap>
  ),
  () => (
    <ShotWrap label="Real AI automation" caption="Real AI automation: checked, saved, ready.">
      <Screen>
        <Browser url="http://localhost:3000"><LandingPage progress={1} /></Browser>
        <div style={{ position: "absolute", top: 96, right: 96, borderRadius: 999, background: `${c.green}33`, color: c.green, border: `1px solid ${c.green}77`, padding: "15px 20px", fontSize: 22, fontWeight: 950 }}>READY</div>
      </Screen>
    </ShotWrap>
  ),
  () => (
    <ShotWrap label="Shell AI OS Controller" caption="Shell AI OS Controller.">
      <CenterHero title="Shell AI OS Controller" subtitle="Build smarter. Automate faster." />
    </ShotWrap>
  ),
  () => (
    <ShotWrap label="Evolve beyond limits" caption="Build smarter. Automate faster. Evolve beyond limits.">
      <Screen title="Workflow summary">
        <div style={{ position: "absolute", inset: 50, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", textAlign: "center", gap: 26 }}>
          <Img src={staticFile("brand/shell-official-logo.png")} style={{ width: 180, height: 180 }} />
          <div style={{ fontSize: 64, fontWeight: 950, lineHeight: 0.96 }}>Real workflow automation.</div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14, width: "100%", marginTop: 12 }}>
            {["Mouse", "Typing", "Browser", "Website", "Terminal", "Files", "Safety", "Logs"].map((item, i) => (
              <div key={item} style={{ borderRadius: 18, border: `1px solid ${i % 2 ? c.green : c.cyan}55`, background: `${i % 2 ? c.green : c.cyan}18`, padding: 18, fontSize: 25, fontWeight: 950 }}>{item}</div>
            ))}
          </div>
        </div>
      </Screen>
    </ShotWrap>
  ),
];

export const ShellInstagramReel = () => (
  <Stage>
    {splitShots.map((Comp, i) => (
      <Sequence key={i} from={i * SHOT} durationInFrames={SHOT}>
        <Comp />
      </Sequence>
    ))}
  </Stage>
);
