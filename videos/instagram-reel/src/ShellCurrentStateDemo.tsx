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

const colors = {
  bg: "#05070B",
  panel: "#0B121A",
  panel2: "#101A25",
  text: "#F8FAFC",
  muted: "#A7B3C8",
  dim: "#65738A",
  cyan: "#40D9F5",
  green: "#64E6AE",
  amber: "#FBBF24",
  red: "#FB7185",
  line: "#263245",
};

const font =
  'Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif';
const mono = '"SFMono-Regular", Consolas, "Liberation Mono", monospace';
const fps = 30;
const shot = 150;

const ease = (frame: number, start: number, duration: number) =>
  interpolate(frame, [start, start + duration], [0, 1], {
    easing: Easing.bezier(0.16, 1, 0.3, 1),
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

const fadeOut = (frame: number, duration: number) =>
  interpolate(frame, [duration - 18, duration], [1, 0], {
    easing: Easing.in(Easing.cubic),
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

const sectionTitle: CSSProperties = {
  color: colors.muted,
  fontFamily: font,
  fontSize: 18,
  fontWeight: 900,
  letterSpacing: 1.6,
  textTransform: "uppercase",
};

const caption: CSSProperties = {
  position: "absolute",
  left: 46,
  right: 46,
  bottom: 54,
  minHeight: 68,
  borderRadius: 18,
  border: "1px solid rgba(255,255,255,0.13)",
  background: "rgba(5,7,11,0.82)",
  color: colors.text,
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  padding: "12px 18px",
  textAlign: "center",
  fontSize: 24,
  fontWeight: 900,
  lineHeight: 1.14,
};

const Stage = ({ children }: { children: ReactNode }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const scan = (frame * 4) % 1280;
  return (
    <AbsoluteFill style={{ backgroundColor: colors.bg, color: colors.text, fontFamily: font }}>
      <AbsoluteFill
        style={{
          background:
            "radial-gradient(circle at 20% 8%, rgba(64,217,245,0.24), transparent 32%), radial-gradient(circle at 90% 70%, rgba(100,230,174,0.15), transparent 34%), linear-gradient(168deg, #05070B, #08111A 56%, #0F1118)",
        }}
      />
      <AbsoluteFill
        style={{
          opacity: 0.22,
          backgroundImage:
            "linear-gradient(rgba(255,255,255,0.045) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.04) 1px, transparent 1px)",
          backgroundSize: "46px 46px",
        }}
      />
      <div
        style={{
          position: "absolute",
          top: scan - 120,
          left: 0,
          right: 0,
          height: 120,
          background: "linear-gradient(180deg, transparent, rgba(64,217,245,0.10), transparent)",
        }}
      />
      {children}
      <Progress />
      <AudioSuite />
    </AbsoluteFill>
  );
};

const AudioSuite = () => (
  <>
    <Audio src={staticFile("audio/os-ambient-bed.wav")} loop volume={0.18} />
    <Sequence from={0}>
      <Audio src={staticFile("audio/boot-chime.wav")} volume={0.46} />
    </Sequence>
    {[shot - 4, shot * 2 - 4, shot * 3 - 4, shot * 4 - 4, shot * 5 - 4].map((from) => (
      <Sequence key={from} from={from}>
        <Audio src={staticFile("audio/data-whoosh.wav")} volume={0.24} />
      </Sequence>
    ))}
    {[84, 236, 394, 584, 752].map((from) => (
      <Sequence key={`click-${from}`} from={from}>
        <Audio src={staticFile("audio/ui-click.wav")} volume={0.20} />
      </Sequence>
    ))}
  </>
);

const Progress = () => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  return (
    <div
      style={{
        position: "absolute",
        left: 46,
        right: 46,
        bottom: 30,
        height: 5,
        borderRadius: 999,
        background: "rgba(255,255,255,0.13)",
        overflow: "hidden",
      }}
    >
      <div
        style={{
          width: `${(frame / Math.max(1, durationInFrames - 1)) * 100}%`,
          height: "100%",
          background: `linear-gradient(90deg, ${colors.cyan}, ${colors.green}, ${colors.amber})`,
        }}
      />
    </div>
  );
};

const Shot = ({
  label,
  text,
  children,
}: {
  label: string;
  text: string;
  children: ReactNode;
}) => {
  const frame = useCurrentFrame();
  const enter = ease(frame, 0, 16);
  return (
    <AbsoluteFill
      style={{
        opacity: fadeOut(frame, shot),
        padding: "54px 44px 78px",
        transform: `translateY(${interpolate(enter, [0, 1], [18, 0])}px)`,
      }}
    >
      <Header />
      <div style={{ ...sectionTitle, marginBottom: 14 }}>{label}</div>
      {children}
      <div style={caption}>{text}</div>
    </AbsoluteFill>
  );
};

const Header = () => (
  <div
    style={{
      position: "absolute",
      top: 22,
      left: 44,
      right: 44,
      display: "flex",
      alignItems: "center",
      justifyContent: "space-between",
      color: colors.dim,
      fontSize: 13,
      fontWeight: 900,
      letterSpacing: 1.4,
      textTransform: "uppercase",
    }}
  >
    <span>Shell AI OS Controller</span>
    <span style={{ color: colors.green }}>CI green</span>
  </div>
);

const ShellWindow = ({ children, title = "Shell Web UI" }: { children: ReactNode; title?: string }) => (
  <div
    style={{
      height: 930,
      borderRadius: 24,
      border: "1px solid rgba(255,255,255,0.16)",
      background: "rgba(8,12,18,0.88)",
      boxShadow: "0 28px 90px rgba(0,0,0,0.38)",
      overflow: "hidden",
    }}
  >
    <div
      style={{
        height: 52,
        display: "flex",
        alignItems: "center",
        gap: 12,
        padding: "0 20px",
        borderBottom: "1px solid rgba(255,255,255,0.08)",
        background: "rgba(9,13,20,0.94)",
      }}
    >
      <Img src={staticFile("brand/shell-official-logo.png")} style={{ width: 30, height: 30 }} />
      <span style={{ color: colors.text, fontSize: 17, fontWeight: 900 }}>{title}</span>
      <span style={{ marginLeft: "auto", color: colors.green, fontSize: 13, fontWeight: 900 }}>
        READY
      </span>
    </div>
    <div style={{ position: "relative", height: 878 }}>{children}</div>
  </div>
);

const Screenshot = ({ file }: { file: string }) => (
  <Img
    src={staticFile(`screenshots/${file}`)}
    style={{ width: "100%", height: "100%", objectFit: "cover", filter: "saturate(1.08)" }}
  />
);

const BigMetric = ({ value, label, tone = colors.green }: { value: string; label: string; tone?: string }) => {
  const frame = useCurrentFrame();
  const p = ease(frame, 10, 26);
  return (
    <div
      style={{
        borderRadius: 18,
        border: `1px solid ${tone}66`,
        background: `${tone}19`,
        padding: 18,
        transform: `scale(${interpolate(p, [0, 1], [0.96, 1])})`,
      }}
    >
      <div style={{ color: tone, fontSize: 42, fontWeight: 950, lineHeight: 1 }}>{value}</div>
      <div style={{ color: colors.muted, fontSize: 15, fontWeight: 850, marginTop: 8 }}>{label}</div>
    </div>
  );
};

const Terminal = ({ lines }: { lines: string[] }) => {
  const frame = useCurrentFrame();
  return (
    <div
      style={{
        height: "100%",
        borderRadius: 24,
        background: "rgba(3,7,18,0.95)",
        border: `1px solid ${colors.line}`,
        padding: 22,
      }}
    >
      {lines.map((line, index) => (
        <div
          key={line}
          style={{
            fontFamily: mono,
            fontSize: 21,
            lineHeight: 1.55,
            color: line.includes("passed") || line.includes("success") ? colors.green : colors.text,
            opacity: ease(frame, index * 9, 12),
          }}
        >
          <span style={{ color: colors.cyan }}>$ </span>
          {line}
        </div>
      ))}
    </div>
  );
};

const Intro = () => {
  const frame = useCurrentFrame();
  const pulse = interpolate(Math.sin(frame / 12), [-1, 1], [0.82, 1.08]);
  return (
    <Shot label="Current repo" text="Shell ab current Web UI, tools, agents, Gallery, Telegram aur CI-green state ke saath synced hai.">
      <ShellWindow title="Current Shell build">
        <div style={{ position: "absolute", inset: 46, display: "grid", placeItems: "center", textAlign: "center" }}>
          <div>
            <Img
              src={staticFile("brand/shell-official-logo.png")}
              style={{ width: 142, height: 142, transform: `scale(${pulse})`, marginBottom: 26 }}
            />
            <div style={{ fontSize: 54, fontWeight: 950, lineHeight: 0.98 }}>Shell AI OS Controller</div>
            <div style={{ color: colors.muted, fontSize: 23, fontWeight: 800, lineHeight: 1.18, marginTop: 18 }}>
              React Web UI + PyQt WebEngine + guarded Python automation
            </div>
          </div>
        </div>
      </ShellWindow>
    </Shot>
  );
};

const UiShot = () => (
  <Shot label="Primary interface" text="Dashboard par transcript aur chart dono se Shell ko text commands de sakte ho.">
    <ShellWindow title="Dashboard">
      <Screenshot file="chat-interface.png" />
    </ShellWindow>
  </Shot>
);

const ToolsShot = () => (
  <Shot label="Tools and agents" text="468 tool entries scan hue, 37/37 agents readiness smoke pass hue.">
    <div style={{ display: "grid", gridTemplateRows: "1fr 210px", gap: 18 }}>
      <ShellWindow title="Tool Catalog">
        <Screenshot file="tools-catalog.png" />
      </ShellWindow>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 14 }}>
        <BigMetric value="468" label="catalog entries" />
        <BigMetric value="37/37" label="agents passed" tone={colors.cyan} />
        <BigMetric value="0" label="probe errors" tone={colors.amber} />
      </div>
    </div>
  </Shot>
);

const SettingsShot = () => (
  <Shot label="Settings and remote control" text="API keys, Telegram remote control, scrollable settings aur safety gates ek jagah hain.">
    <ShellWindow title="Settings">
      <Screenshot file="settings-panel.png" />
    </ShellWindow>
  </Shot>
);

const ArchitectureShot = () => (
  <Shot label="Architecture" text="Web UI bridge natural-language router aur tool gateway ko call karta hai; risky actions gated hain.">
    <ShellWindow title="Runtime map">
      <div style={{ position: "absolute", inset: 26, display: "grid", gridTemplateRows: "1fr 1fr", gap: 16 }}>
        {[
          ["React Web UI", "QWebChannel bridge", "Python host"],
          ["NL router", "Tool gateway", "Agents + memory"],
          ["OS control", "Gallery + media", "Telemetry charts"],
        ].map((row, rowIndex) => (
          <div key={row.join("-")} style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 14 }}>
            {row.map((item, index) => (
              <div
                key={item}
                style={{
                  borderRadius: 20,
                  border: `1px solid ${(rowIndex + index) % 2 ? colors.green : colors.cyan}66`,
                  background: `${(rowIndex + index) % 2 ? colors.green : colors.cyan}17`,
                  display: "grid",
                  placeItems: "center",
                  textAlign: "center",
                  padding: 18,
                  fontSize: 25,
                  fontWeight: 950,
                  lineHeight: 1.06,
                }}
              >
                {item}
              </div>
            ))}
          </div>
        ))}
      </div>
    </ShellWindow>
  </Shot>
);

const CiShot = () => (
  <Shot label="Validation" text="GitHub CI/Security green: Python 3.10 se 3.13 tak matrix pass hai.">
    <div style={{ display: "grid", gridTemplateRows: "1fr 190px", gap: 18 }}>
      <Terminal
        lines={[
          "pytest -q",
          "538 passed",
          "CI Python 3.10 success",
          "CI Python 3.11 success",
          "CI Python 3.12 success",
          "CI Python 3.13 success",
          "Security: CodeQL + secret guard success",
        ]}
      />
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
        <BigMetric value="green" label="GitHub Actions" />
        <BigMetric value="safe" label="release-gated defaults" tone={colors.cyan} />
      </div>
    </div>
  </Shot>
);

export const ShellCurrentStateDemo = () => (
  <Stage>
    {[Intro, UiShot, ToolsShot, SettingsShot, ArchitectureShot, CiShot].map((Comp, index) => (
      <Sequence key={index} from={index * shot} durationInFrames={shot}>
        <Comp />
      </Sequence>
    ))}
  </Stage>
);

export const CURRENT_STATE_FPS = fps;
export const CURRENT_STATE_DURATION_FRAMES = shot * 6;
