import type { CSSProperties, ReactNode } from "react";
import { Audio } from "@remotion/media";
import {
  AbsoluteFill,
  Easing,
  Img,
  Sequence,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

const fps = 30;
const shot = 135;

const colors = {
  bg: "#05070B",
  ink: "#F8FAFC",
  muted: "#9AA8BD",
  dim: "#64748B",
  cyan: "#22D3EE",
  cyanSoft: "#67E8F9",
  green: "#64E6AE",
  amber: "#FBBF24",
  panel: "rgba(7, 12, 20, 0.78)",
  line: "rgba(103, 232, 249, 0.28)",
};

const font =
  'Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif';

const ease = (frame: number, start: number, duration: number) =>
  interpolate(frame, [start, start + duration], [0, 1], {
    easing: Easing.bezier(0.16, 1, 0.3, 1),
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

const softOut = (frame: number, duration: number) =>
  interpolate(frame, [duration - 18, duration], [1, 0], {
    easing: Easing.in(Easing.cubic),
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

const Stage = ({ children }: { children: ReactNode }) => {
  const frame = useCurrentFrame();
  const sweep = (frame * 3) % 1080;
  return (
    <AbsoluteFill style={{ backgroundColor: colors.bg, color: colors.ink, fontFamily: font }}>
      <AbsoluteFill
        style={{
          background:
            "radial-gradient(circle at 18% 18%, rgba(34,211,238,0.22), transparent 28%), radial-gradient(circle at 86% 64%, rgba(100,230,174,0.13), transparent 30%), linear-gradient(145deg, #05070B, #08111A 52%, #061E25)",
        }}
      />
      <AbsoluteFill
        style={{
          opacity: 0.2,
          backgroundImage:
            "linear-gradient(rgba(255,255,255,0.05) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.04) 1px, transparent 1px)",
          backgroundSize: "54px 54px",
        }}
      />
      <div
        style={{
          position: "absolute",
          top: sweep - 140,
          left: 0,
          right: 0,
          height: 140,
          background: "linear-gradient(180deg, transparent, rgba(103,232,249,0.10), transparent)",
        }}
      />
      <Audio src={staticFile("audio/os-ambient-bed.wav")} loop volume={0.14} />
      <Sequence from={0}>
        <Audio src={staticFile("audio/boot-chime.wav")} volume={0.38} />
      </Sequence>
      {[shot - 8, shot * 2 - 8, shot * 3 - 8, shot * 4 - 8, shot * 5 - 8, shot * 6 - 8].map(
        (from) => (
          <Sequence key={from} from={from}>
            <Audio src={staticFile("audio/data-whoosh.wav")} volume={0.18} />
          </Sequence>
        ),
      )}
      {children}
      <Progress />
    </AbsoluteFill>
  );
};

const Progress = () => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  return (
    <div
      style={{
        position: "absolute",
        left: 76,
        right: 76,
        bottom: 36,
        height: 5,
        borderRadius: 999,
        background: "rgba(255,255,255,0.12)",
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

const Header = () => (
  <div
    style={{
      position: "absolute",
      top: 34,
      left: 72,
      right: 72,
      display: "flex",
      alignItems: "center",
      justifyContent: "space-between",
      color: colors.dim,
      fontSize: 18,
      fontWeight: 900,
      letterSpacing: 2.8,
      textTransform: "uppercase",
    }}
  >
    <span>Shell AI OS Controller</span>
    <span style={{ color: colors.green }}>CI green · local-first</span>
  </div>
);

const ShellLogo = ({ size = 96 }: { size?: number }) => (
  <div
    style={{
      width: size,
      height: size,
      borderRadius: size * 0.22,
      display: "grid",
      placeItems: "center",
      background: "linear-gradient(135deg, #67E8F9, #8EA4FF)",
      boxShadow: "0 0 42px rgba(34,211,238,0.36)",
      color: "#06111A",
      fontSize: size * 0.46,
      fontWeight: 950,
    }}
  >
    S
  </div>
);

const TextBlock = ({
  eyebrow,
  title,
  body,
}: {
  eyebrow: string;
  title: string;
  body: string;
}) => {
  const frame = useCurrentFrame();
  const enter = spring({ frame, fps, config: { damping: 20, stiffness: 120 } });
  return (
    <div
      style={{
        transform: `translateY(${interpolate(enter, [0, 1], [28, 0])}px)`,
        opacity: enter,
      }}
    >
      <div
        style={{
          color: colors.cyanSoft,
          fontSize: 18,
          fontWeight: 950,
          letterSpacing: 4,
          textTransform: "uppercase",
          marginBottom: 20,
        }}
      >
        {eyebrow}
      </div>
      <div
        style={{
          fontSize: 58,
          lineHeight: 0.98,
          fontWeight: 950,
          letterSpacing: 0,
          marginBottom: 24,
        }}
      >
        {title}
      </div>
      <div style={{ color: colors.muted, fontSize: 25, lineHeight: 1.22, fontWeight: 650 }}>
        {body}
      </div>
    </div>
  );
};

const ChromeFrame = ({
  file,
  title,
  scale = 1,
}: {
  file: string;
  title: string;
  scale?: number;
}) => {
  const frame = useCurrentFrame();
  const enter = ease(frame, 6, 22);
  return (
    <div
      style={{
        height: 760,
        borderRadius: 24,
        border: `1px solid ${colors.line}`,
        background: "rgba(5, 9, 17, 0.88)",
        boxShadow: "0 30px 110px rgba(0,0,0,0.45)",
        overflow: "hidden",
        transform: `scale(${interpolate(enter, [0, 1], [0.97, scale])})`,
        opacity: enter,
      }}
    >
      <div
        style={{
          height: 56,
          display: "flex",
          alignItems: "center",
          gap: 14,
          padding: "0 22px",
          borderBottom: "1px solid rgba(255,255,255,0.08)",
          background: "rgba(4, 8, 14, 0.96)",
        }}
      >
        <ShellLogo size={30} />
        <span style={{ fontSize: 17, fontWeight: 950 }}>{title}</span>
        <span style={{ marginLeft: "auto", color: colors.green, fontSize: 14, fontWeight: 900 }}>
          READY
        </span>
      </div>
      <Img
        src={staticFile(`current-ui/${file}`)}
        style={{ width: "100%", height: 704, objectFit: "contain", backgroundColor: "#050914" }}
      />
    </div>
  );
};

const Metric = ({ value, label, tone = colors.cyan }: { value: string; label: string; tone?: string }) => {
  const frame = useCurrentFrame();
  const enter = ease(frame, 18, 24);
  return (
    <div
      style={{
        borderRadius: 22,
        border: `1px solid ${tone}66`,
        background: `${tone}18`,
        padding: "24px 26px",
        opacity: enter,
        transform: `translateY(${interpolate(enter, [0, 1], [18, 0])}px)`,
      }}
    >
      <div style={{ color: tone, fontSize: 48, fontWeight: 950, lineHeight: 1 }}>{value}</div>
      <div
        style={{
          color: colors.muted,
          fontSize: 15,
          fontWeight: 900,
          letterSpacing: 2,
          textTransform: "uppercase",
          marginTop: 10,
        }}
      >
        {label}
      </div>
    </div>
  );
};

const Shot = ({ children }: { children: ReactNode }) => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill style={{ opacity: softOut(frame, shot), padding: "92px 72px 72px" }}>
      <Header />
      {children}
    </AbsoluteFill>
  );
};

const Hero = () => {
  const frame = useCurrentFrame();
  const pulse = interpolate(Math.sin(frame / 16), [-1, 1], [0.96, 1.04]);
  return (
    <Shot>
      <div
        style={{
          height: "100%",
          display: "grid",
          gridTemplateColumns: "0.9fr 1.1fr",
          gap: 54,
          alignItems: "center",
        }}
      >
        <div>
          <div style={{ transform: `scale(${pulse})`, transformOrigin: "left center", marginBottom: 36 }}>
            <ShellLogo size={128} />
          </div>
          <TextBlock
            eyebrow="Current public demo"
            title="Shell AI OS Controller"
            body="A local-first desktop control layer for chat, voice, tools, automation, telemetry, and runtime diagnostics."
          />
        </div>
        <ChromeFrame file="dashboard.svg" title="Current Dashboard" />
      </div>
    </Shot>
  );
};

const Dashboard = () => (
  <Shot>
    <div style={{ display: "grid", gridTemplateColumns: "1.25fr 0.75fr", gap: 42, alignItems: "center" }}>
      <ChromeFrame file="dashboard.svg" title="System Dashboard" />
      <TextBlock
        eyebrow="Runtime visibility"
        title="Telemetry, transcript, and chart control in one workspace."
        body="Shell shows live system state while keeping typed chart and transcript commands text-only by default."
      />
    </div>
  </Shot>
);

const ChatChart = () => (
  <Shot>
    <div style={{ display: "grid", gridTemplateColumns: "0.74fr 1.26fr", gap: 42, alignItems: "center" }}>
      <TextBlock
        eyebrow="Chat and chart"
        title="Ask questions or run tools from the same command lane."
        body="Calculator, unit conversion, memory recall, and chart prompts all route through the guarded backend."
      />
      <ChromeFrame file="chat-chart.svg" title="Chat + Chart" />
    </div>
  </Shot>
);

const VoiceTools = () => (
  <Shot>
    <div style={{ display: "grid", gridTemplateColumns: "1.15fr 0.85fr", gap: 42, alignItems: "center" }}>
      <ChromeFrame file="voice-tools.svg" title="Voice Core" />
      <TextBlock
        eyebrow="Voice pipeline"
        title="Voice stays optional, visible, and controllable."
        body="Manual voice controls remain available, with wake word, VAD, and local STT kept behind explicit flags."
      />
    </div>
  </Shot>
);

const Tools = () => (
  <Shot>
    <div style={{ display: "grid", gridTemplateColumns: "0.76fr 1.24fr", gap: 42, alignItems: "center" }}>
      <div>
        <TextBlock
          eyebrow="Tool gateway"
          title="Hundreds of local tools without silent risk."
          body="Tool execution is routed through a catalog, readiness checks, safety gates, and clear result panels."
        />
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 18, marginTop: 34 }}>
          <Metric value="468" label="catalog entries" />
          <Metric value="37/37" label="agents verified" tone={colors.green} />
        </div>
      </div>
      <ChromeFrame file="tools-control.svg" title="Tools / MCP" />
    </div>
  </Shot>
);

const SettingsGallery = () => (
  <Shot>
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 34, alignItems: "center" }}>
      <ChromeFrame file="settings-api.svg" title="Settings + API Keys" scale={0.98} />
      <ChromeFrame file="gallery-media.svg" title="Gallery + Media" scale={0.98} />
    </div>
  </Shot>
);

const Architecture = () => (
  <Shot>
    <div style={{ display: "grid", gridTemplateColumns: "1.18fr 0.82fr", gap: 42, alignItems: "center" }}>
      <ChromeFrame file="runtime-architecture.svg" title="Runtime Architecture" />
      <TextBlock
        eyebrow="Architecture"
        title="React UI, Python runtime, and safe local automation."
        body="The Web UI talks to Shell Hub through QWebChannel, then routes requests through the NL router, tools, agents, memory, RAG, and OS drivers."
      />
    </div>
  </Shot>
);

const Final = () => (
  <Shot>
    <div
      style={{
        height: "100%",
        display: "grid",
        gridTemplateColumns: "0.9fr 1.1fr",
        gap: 54,
        alignItems: "center",
      }}
    >
      <div>
        <TextBlock
          eyebrow="Repository-ready"
          title="Current UI media, docs, and release status are aligned."
          body="Use the landscape demo, SVG showcase, media kit, architecture map, and CI-green status for the public GitHub presentation."
        />
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 18, marginTop: 34 }}>
          <Metric value="538" label="tests passed" tone={colors.green} />
          <Metric value="3.10-3.13" label="Python matrix" />
          <Metric value="safe" label="gated actions" tone={colors.amber} />
        </div>
      </div>
      <ChromeFrame file="dashboard.svg" title="Shell Web UI" />
    </div>
  </Shot>
);

export const ShellCurrentUiLandscape = () => (
  <Stage>
    {[Hero, Dashboard, ChatChart, VoiceTools, Tools, SettingsGallery, Architecture, Final].map(
      (Comp, index) => (
        <Sequence key={index} from={index * shot} durationInFrames={shot}>
          <Comp />
        </Sequence>
      ),
    )}
  </Stage>
);

export const CURRENT_UI_LANDSCAPE_FPS = fps;
export const CURRENT_UI_LANDSCAPE_DURATION_FRAMES = shot * 8;
