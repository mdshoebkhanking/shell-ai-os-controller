import type { ReactNode } from "react";
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
const scene = 96;

const palette = {
  bg: "#07090D",
  panel: "rgba(18, 23, 31, 0.72)",
  panelStrong: "rgba(10, 14, 22, 0.92)",
  line: "rgba(180, 210, 255, 0.18)",
  lineStrong: "rgba(145, 190, 255, 0.38)",
  ink: "#F7FAFF",
  muted: "#A9B5C8",
  dim: "#647084",
  cyan: "#54D7FF",
  blue: "#4F8CFF",
  mint: "#7CFFBF",
  silver: "#D7E3F4",
  warm: "#FFCC75",
};

const font =
  'Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif';

const ease = (frame: number, start: number, duration: number) =>
  interpolate(frame, [start, start + duration], [0, 1], {
    easing: Easing.bezier(0.16, 1, 0.3, 1),
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

const outro = (frame: number, duration = scene) =>
  interpolate(frame, [duration - 14, duration], [1, 0], {
    easing: Easing.in(Easing.cubic),
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

const Logo = ({ size = 58 }: { size?: number }) => (
  <Img
    src={staticFile("brand/shell-official-logo.png")}
    style={{
      width: size,
      height: size,
      objectFit: "contain",
      filter: "drop-shadow(0 0 28px rgba(84, 215, 255, 0.38))",
    }}
  />
);

const Stage = ({ children }: { children: ReactNode }) => {
  const frame = useCurrentFrame();
  const sweep = (frame * 2.2) % 1260;
  return (
    <AbsoluteFill style={{ backgroundColor: palette.bg, color: palette.ink, fontFamily: font }}>
      <AbsoluteFill
        style={{
          background:
            "linear-gradient(135deg, #05070B 0%, #10141E 46%, #05080E 100%)",
        }}
      />
      <AbsoluteFill
        style={{
          background:
            "radial-gradient(circle at 20% 8%, rgba(84,215,255,0.20), transparent 28%), radial-gradient(circle at 85% 76%, rgba(79,140,255,0.15), transparent 34%), linear-gradient(100deg, transparent, rgba(255,255,255,0.05), transparent)",
        }}
      />
      <AbsoluteFill
        style={{
          opacity: 0.2,
          backgroundImage:
            "linear-gradient(rgba(180,210,255,0.07) 1px, transparent 1px), linear-gradient(90deg, rgba(180,210,255,0.06) 1px, transparent 1px)",
          backgroundSize: "72px 72px",
          transform: `translateY(${interpolate(frame, [0, 300], [0, -72], {
            extrapolateRight: "extend",
          })}px)`,
        }}
      />
      <div
        style={{
          position: "absolute",
          top: sweep - 260,
          left: -120,
          right: -120,
          height: 190,
          transform: "rotate(-8deg)",
          background:
            "linear-gradient(180deg, transparent, rgba(84,215,255,0.13), rgba(255,255,255,0.08), transparent)",
          filter: "blur(4px)",
        }}
      />
      <Audio src={staticFile("audio/os-ambient-bed.wav")} loop volume={0.1} />
      <Sequence from={0}>
        <Audio src={staticFile("audio/boot-chime.wav")} volume={0.22} />
      </Sequence>
      {[scene - 7, scene * 2 - 7, scene * 3 - 7, scene * 4 - 7, scene * 5 - 7, scene * 6 - 7].map(
        (from) => (
          <Sequence key={from} from={from}>
            <Audio src={staticFile("audio/data-whoosh.wav")} volume={0.12} />
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
        left: 80,
        right: 80,
        bottom: 42,
        height: 3,
        borderRadius: 999,
        background: "rgba(255,255,255,0.10)",
        overflow: "hidden",
      }}
    >
      <div
        style={{
          width: `${(frame / Math.max(1, durationInFrames - 1)) * 100}%`,
          height: "100%",
          background: `linear-gradient(90deg, ${palette.cyan}, ${palette.blue}, ${palette.mint})`,
          boxShadow: "0 0 24px rgba(84,215,255,0.7)",
        }}
      />
    </div>
  );
};

const Header = () => (
  <div
    style={{
      position: "absolute",
      top: 38,
      left: 76,
      right: 76,
      display: "flex",
      alignItems: "center",
      justifyContent: "space-between",
      color: palette.dim,
      fontSize: 15,
      fontWeight: 850,
      letterSpacing: 0,
      textTransform: "uppercase",
    }}
  >
    <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
      <Logo size={34} />
      <span>Shell AI OS Controller</span>
    </div>
    <span style={{ color: palette.cyan }}>Real UI Capture</span>
  </div>
);

const SceneShell = ({ children }: { children: ReactNode }) => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill style={{ opacity: outro(frame), padding: "96px 76px 74px" }}>
      <Header />
      {children}
    </AbsoluteFill>
  );
};

const Kicker = ({ text }: { text: string }) => (
  <div
    style={{
      display: "inline-flex",
      alignItems: "center",
      gap: 10,
      padding: "9px 14px",
      borderRadius: 999,
      border: `1px solid ${palette.lineStrong}`,
      background: "rgba(255,255,255,0.06)",
      color: palette.cyan,
      fontSize: 15,
      fontWeight: 900,
      textTransform: "uppercase",
      letterSpacing: 0,
      marginBottom: 20,
    }}
  >
    <span
      style={{
        width: 8,
        height: 8,
        borderRadius: 999,
        background: palette.mint,
        boxShadow: `0 0 18px ${palette.mint}`,
      }}
    />
    {text}
  </div>
);

const TitleBlock = ({
  kicker,
  title,
  body,
  compact = false,
}: {
  kicker: string;
  title: string;
  body: string;
  compact?: boolean;
}) => {
  const frame = useCurrentFrame();
  const enter = spring({ frame, fps, config: { damping: 22, stiffness: 132 } });
  return (
    <div
      style={{
        opacity: enter,
        transform: `translateY(${interpolate(enter, [0, 1], [30, 0])}px)`,
      }}
    >
      <Kicker text={kicker} />
      <div
        style={{
          maxWidth: compact ? 590 : 760,
          fontSize: compact ? 54 : 72,
          lineHeight: compact ? 1.02 : 0.94,
          fontWeight: 950,
          letterSpacing: 0,
          marginBottom: 22,
          textShadow: "0 18px 80px rgba(0,0,0,0.55)",
        }}
      >
        {title}
      </div>
      <div
        style={{
          maxWidth: compact ? 560 : 670,
          color: palette.muted,
          fontSize: compact ? 22 : 25,
          lineHeight: 1.25,
          fontWeight: 650,
        }}
      >
        {body}
      </div>
    </div>
  );
};

const GlassFrame = ({
  file,
  title,
  variant = "contain",
  scale = 1,
  lift = 0,
  shadow = "blue",
}: {
  file: string;
  title: string;
  variant?: "contain" | "cover";
  scale?: number;
  lift?: number;
  shadow?: "blue" | "mint" | "silver";
}) => {
  const frame = useCurrentFrame();
  const enter = ease(frame, 5, 24);
  const drift = interpolate(frame, [0, scene], [0, lift]);
  const glow =
    shadow === "mint"
      ? "rgba(124,255,191,0.24)"
      : shadow === "silver"
        ? "rgba(215,227,244,0.22)"
        : "rgba(84,215,255,0.25)";
  return (
    <div
      style={{
        borderRadius: 30,
        padding: 12,
        border: `1px solid ${palette.lineStrong}`,
        background:
          "linear-gradient(145deg, rgba(255,255,255,0.18), rgba(255,255,255,0.04) 38%, rgba(255,255,255,0.10))",
        boxShadow: `0 38px 130px rgba(0,0,0,0.58), 0 0 70px ${glow}`,
        overflow: "hidden",
        opacity: enter,
        transform: `translateY(${interpolate(enter, [0, 1], [34, 0]) + drift}px) scale(${interpolate(
          enter,
          [0, 1],
          [0.96, scale],
        )})`,
      }}
    >
      <div
        style={{
          height: 54,
          display: "flex",
          alignItems: "center",
          gap: 14,
          padding: "0 18px",
          borderRadius: 22,
          color: palette.silver,
          background: "rgba(4, 7, 12, 0.82)",
          border: "1px solid rgba(255,255,255,0.08)",
          marginBottom: 10,
        }}
      >
        <Logo size={28} />
        <span style={{ fontSize: 16, fontWeight: 920 }}>{title}</span>
        <span
          style={{
            marginLeft: "auto",
            color: palette.mint,
            fontSize: 12,
            fontWeight: 900,
            letterSpacing: 0,
            textTransform: "uppercase",
          }}
        >
          Live surface
        </span>
      </div>
      <Img
        src={staticFile(`current-ui/${file}`)}
        style={{
          width: "100%",
          height: "100%",
          maxHeight: 720,
          borderRadius: 22,
          objectFit: variant,
          background: "#05070B",
        }}
      />
    </div>
  );
};

const StatPill = ({ value, label, tone = palette.cyan }: { value: string; label: string; tone?: string }) => {
  const frame = useCurrentFrame();
  const enter = ease(frame, 22, 20);
  return (
    <div
      style={{
        borderRadius: 18,
        border: `1px solid ${tone}55`,
        background: `${tone}18`,
        padding: "18px 20px",
        opacity: enter,
        transform: `translateY(${interpolate(enter, [0, 1], [18, 0])}px)`,
      }}
    >
      <div style={{ color: tone, fontSize: 38, lineHeight: 1, fontWeight: 950 }}>{value}</div>
      <div
        style={{
          color: palette.muted,
          fontSize: 13,
          fontWeight: 900,
          textTransform: "uppercase",
          marginTop: 8,
        }}
      >
        {label}
      </div>
    </div>
  );
};

const FloatingCard = ({
  title,
  body,
  index,
  tone = palette.cyan,
}: {
  title: string;
  body: string;
  index: number;
  tone?: string;
}) => {
  const frame = useCurrentFrame();
  const enter = ease(frame, 10 + index * 8, 20);
  return (
    <div
      style={{
        borderRadius: 22,
        border: `1px solid ${tone}44`,
        background: "rgba(9, 13, 22, 0.76)",
        backdropFilter: "blur(18px)",
        padding: "20px 22px",
        boxShadow: "0 24px 80px rgba(0,0,0,0.38)",
        opacity: enter,
        transform: `translateX(${interpolate(enter, [0, 1], [40, 0])}px)`,
      }}
    >
      <div style={{ color: tone, fontSize: 15, fontWeight: 950, textTransform: "uppercase" }}>{title}</div>
      <div style={{ color: palette.ink, fontSize: 23, fontWeight: 850, marginTop: 8, lineHeight: 1.16 }}>
        {body}
      </div>
    </div>
  );
};

const Hero = () => {
  const frame = useCurrentFrame();
  const imageMove = interpolate(frame, [0, scene], [1.02, 1.075]);
  const titleEnter = ease(frame, 8, 24);
  return (
    <SceneShell>
      <div
        style={{
          position: "absolute",
          inset: "116px 76px 90px",
          borderRadius: 38,
          overflow: "hidden",
          border: `1px solid ${palette.lineStrong}`,
          boxShadow: "0 42px 150px rgba(0,0,0,0.62)",
        }}
      >
        <Img
          src={staticFile("current-ui/dashboard.png")}
          style={{
            width: "100%",
            height: "100%",
            objectFit: "cover",
            transform: `scale(${imageMove})`,
            filter: "brightness(0.55) saturate(1.12)",
          }}
        />
        <AbsoluteFill
          style={{
            background:
              "linear-gradient(90deg, rgba(5,7,11,0.94) 0%, rgba(5,7,11,0.76) 34%, rgba(5,7,11,0.24) 100%)",
          }}
        />
      </div>
      <div
        style={{
          position: "absolute",
          left: 140,
          top: 255,
          opacity: titleEnter,
          transform: `translateY(${interpolate(titleEnter, [0, 1], [28, 0])}px)`,
        }}
      >
        <Logo size={104} />
        <div style={{ marginTop: 28 }}>
          <TitleBlock
            kicker="Desktop AI OS"
            title="Shell AI"
            body="A real desktop control interface for chat, voice, tools, apps, files, and generated media."
          />
        </div>
      </div>
      <div
        style={{
          position: "absolute",
          right: 138,
          bottom: 136,
          display: "grid",
          gridTemplateColumns: "1fr 1fr 1fr",
          gap: 14,
          width: 510,
        }}
      >
        <StatPill value="490" label="tools" />
        <StatPill value="40" label="agents" tone={palette.mint} />
        <StatPill value="16:9" label="demo" tone={palette.warm} />
      </div>
    </SceneShell>
  );
};

const Dashboard = () => (
  <SceneShell>
    <div style={{ display: "grid", gridTemplateColumns: "1.2fr 0.8fr", gap: 42, alignItems: "center" }}>
      <GlassFrame file="dashboard.png" title="Dashboard + Transcript" scale={1.01} />
      <div style={{ display: "grid", gap: 18 }}>
        <TitleBlock
          kicker="Live workspace"
          title="Talk to the system. See the work move."
          body="The dashboard keeps conversation, voice controls, telemetry, and activity visible in one focused surface."
          compact
        />
        <FloatingCard title="01 Prompt" body="Ask Shell from chat or voice." index={0} />
        <FloatingCard title="02 Route" body="Intent maps to tools and agents." index={1} tone={palette.blue} />
        <FloatingCard title="03 Result" body="Responses stay visible and controlled." index={2} tone={palette.mint} />
      </div>
    </div>
  </SceneShell>
);

const Control = () => (
  <SceneShell>
    <div style={{ display: "grid", gridTemplateColumns: "0.72fr 1.28fr", gap: 42, alignItems: "center" }}>
      <div>
        <TitleBlock
          kicker="Control center"
          title="Tools, agents, and guarded actions in one place."
          body="The current UI exposes desktop control, Windows MCP, media, memory, browser, and developer workflows without hiding the routing layer."
          compact
        />
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginTop: 28 }}>
          <StatPill value="433" label="tools" />
          <StatPill value="17" label="actions" tone={palette.warm} />
        </div>
      </div>
      <GlassFrame file="control.png" title="Backend Control" scale={1.02} shadow="mint" />
    </div>
  </SceneShell>
);

const ImageFlow = () => (
  <SceneShell>
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 36, alignItems: "center" }}>
      <GlassFrame file="gallery.png" title="Gallery / Generated Media" scale={0.98} shadow="silver" />
      <div style={{ display: "grid", gap: 18 }}>
        <TitleBlock
          kicker="Image generation"
          title="Prompt. Generate. Save to Gallery."
          body="Generated images flow back into Shell's visual vault so the app feels like it is doing the work, not just talking about it."
          compact
        />
        <FloatingCard title="Animation" body="Progress state appears in the UI." index={0} tone={palette.mint} />
        <FloatingCard title="Artifact" body="Result is saved as a gallery item." index={1} tone={palette.cyan} />
      </div>
    </div>
  </SceneShell>
);

const Workspace = () => {
  const frame = useCurrentFrame();
  const cards = [
    { file: "apps.png", title: "Apps" },
    { file: "notes.png", title: "Notes" },
    { file: "phone.png", title: "Phone" },
  ];
  return (
    <SceneShell>
      <div style={{ display: "grid", gridTemplateColumns: "0.86fr 1.14fr", gap: 40, alignItems: "center" }}>
        <TitleBlock
          kicker="Daily workspace"
          title="Apps, notes, device links, and memory stay close."
          body="Every tab uses the same compact Shell chrome, so users can move between workflows without losing context."
          compact
        />
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 18 }}>
          {cards.map((card, index) => {
            const enter = ease(frame, 8 + index * 8, 22);
            return (
              <div
                key={card.file}
                style={{
                  borderRadius: 24,
                  border: `1px solid ${palette.line}`,
                  background: palette.panel,
                  padding: 10,
                  opacity: enter,
                  transform: `translateY(${interpolate(enter, [0, 1], [42, index === 1 ? -20 : 12])}px)`,
                  boxShadow: "0 28px 90px rgba(0,0,0,0.42)",
                }}
              >
                <Img
                  src={staticFile(`current-ui/${card.file}`)}
                  style={{ width: "100%", height: 478, objectFit: "cover", borderRadius: 18 }}
                />
                <div
                  style={{
                    padding: "16px 4px 8px",
                    color: palette.ink,
                    textAlign: "center",
                    fontSize: 22,
                    fontWeight: 920,
                  }}
                >
                  {card.title}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </SceneShell>
  );
};

const Automation = () => (
  <SceneShell>
    <div style={{ display: "grid", gridTemplateColumns: "1.16fr 0.84fr", gap: 42, alignItems: "center" }}>
      <GlassFrame file="macros.png" title="Macros / Automation" scale={1.02} />
      <div style={{ display: "grid", gap: 18 }}>
        <TitleBlock
          kicker="Automation"
          title="Build repeatable actions visually."
          body="Macro modules make desktop workflows feel structured: trigger, app action, voice, browser, communication, and mobile link."
          compact
        />
        <FloatingCard title="Trigger" body="Start from user intent." index={0} />
        <FloatingCard title="Action" body="Route to system modules." index={1} tone={palette.mint} />
        <FloatingCard title="Run" body="Execute with clear state." index={2} tone={palette.warm} />
      </div>
    </div>
  </SceneShell>
);

const Trust = () => (
  <SceneShell>
    <div style={{ display: "grid", gridTemplateColumns: "0.8fr 1.2fr", gap: 42, alignItems: "center" }}>
      <div>
        <TitleBlock
          kicker="Settings"
          title="Keys, runtime, and updates stay explicit."
          body="The settings surface is built for real desktop use: provider keys, voice defaults, updates, and local runtime control."
          compact
        />
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginTop: 28 }}>
          <StatPill value="local" label="runtime" tone={palette.mint} />
          <StatPill value="safe" label="media" tone={palette.silver} />
        </div>
      </div>
      <GlassFrame file="settings.png" title="Command Center" scale={1.02} shadow="silver" />
    </div>
  </SceneShell>
);

const Final = () => {
  const frame = useCurrentFrame();
  const enter = ease(frame, 5, 24);
  return (
    <SceneShell>
      <div
        style={{
          position: "absolute",
          inset: "122px 110px 112px",
          borderRadius: 42,
          overflow: "hidden",
          border: `1px solid ${palette.lineStrong}`,
          boxShadow: "0 48px 160px rgba(0,0,0,0.68)",
          opacity: enter,
          transform: `scale(${interpolate(enter, [0, 1], [0.98, 1])})`,
        }}
      >
        <Img
          src={staticFile("current-ui/dashboard.png")}
          style={{
            width: "100%",
            height: "100%",
            objectFit: "cover",
            filter: "brightness(0.48) saturate(1.16)",
          }}
        />
        <AbsoluteFill style={{ background: "rgba(4, 7, 12, 0.56)" }} />
      </div>
      <div
        style={{
          position: "absolute",
          inset: 0,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          textAlign: "center",
          flexDirection: "column",
          opacity: enter,
        }}
      >
        <Logo size={124} />
        <div style={{ fontSize: 78, lineHeight: 0.96, fontWeight: 950, letterSpacing: 0, marginTop: 28 }}>
          Shell AI OS Controller
        </div>
        <div style={{ color: palette.cyan, fontSize: 26, fontWeight: 850, marginTop: 18 }}>
          Chat. Voice. Tools. Gallery. Desktop control.
        </div>
      </div>
    </SceneShell>
  );
};

export const ShellCurrentUiLandscape = () => (
  <Stage>
    {[Hero, Dashboard, Control, ImageFlow, Workspace, Automation, Trust, Final].map((Comp, index) => (
      <Sequence key={index} from={index * scene} durationInFrames={scene}>
        <Comp />
      </Sequence>
    ))}
  </Stage>
);

export const CURRENT_UI_LANDSCAPE_FPS = fps;
export const CURRENT_UI_LANDSCAPE_DURATION_FRAMES = scene * 8;
