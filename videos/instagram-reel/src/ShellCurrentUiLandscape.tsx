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
  bg: "#050706",
  ink: "#F4FFF8",
  muted: "#A8BFAF",
  dim: "#607869",
  emerald: "#22C55E",
  neon: "#75FF9A",
  amber: "#FBBF24",
  line: "rgba(117, 255, 154, 0.28)",
  panel: "rgba(4, 10, 8, 0.82)",
};

const font =
  'Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif';

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

const Stage = ({ children }: { children: ReactNode }) => {
  const frame = useCurrentFrame();
  const scan = (frame * 2.8) % 1120;
  return (
    <AbsoluteFill style={{ backgroundColor: colors.bg, color: colors.ink, fontFamily: font }}>
      <AbsoluteFill
        style={{
          background:
            "radial-gradient(circle at 18% 16%, rgba(34,197,94,0.20), transparent 30%), radial-gradient(circle at 84% 72%, rgba(117,255,154,0.12), transparent 32%), linear-gradient(145deg, #030503, #07110B 54%, #03120A)",
        }}
      />
      <AbsoluteFill
        style={{
          opacity: 0.16,
          backgroundImage:
            "linear-gradient(rgba(117,255,154,0.08) 1px, transparent 1px), linear-gradient(90deg, rgba(117,255,154,0.06) 1px, transparent 1px)",
          backgroundSize: "60px 60px",
        }}
      />
      <div
        style={{
          position: "absolute",
          top: scan - 180,
          left: 0,
          right: 0,
          height: 170,
          background: "linear-gradient(180deg, transparent, rgba(117,255,154,0.13), transparent)",
        }}
      />
      <Audio src={staticFile("audio/os-ambient-bed.wav")} loop volume={0.12} />
      <Sequence from={0}>
        <Audio src={staticFile("audio/boot-chime.wav")} volume={0.3} />
      </Sequence>
      {[shot - 8, shot * 2 - 8, shot * 3 - 8, shot * 4 - 8, shot * 5 - 8, shot * 6 - 8].map(
        (from) => (
          <Sequence key={from} from={from}>
            <Audio src={staticFile("audio/data-whoosh.wav")} volume={0.14} />
          </Sequence>
        ),
      )}
      {children}
      <Progress />
    </AbsoluteFill>
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
      fontSize: 17,
      fontWeight: 900,
      letterSpacing: 0,
      textTransform: "uppercase",
    }}
  >
    <span>Shell AI OS Controller</span>
    <span style={{ color: colors.neon }}>Actual UI capture · PyQt WebEngine</span>
  </div>
);

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
        background: "rgba(255,255,255,0.10)",
        overflow: "hidden",
      }}
    >
      <div
        style={{
          width: `${(frame / Math.max(1, durationInFrames - 1)) * 100}%`,
          height: "100%",
          background: `linear-gradient(90deg, ${colors.emerald}, ${colors.neon}, ${colors.amber})`,
        }}
      />
    </div>
  );
};

const Logo = ({ size = 78 }: { size?: number }) => (
  <Img
    src={staticFile("brand/shell-official-logo.png")}
    style={{
      width: size,
      height: size,
      objectFit: "contain",
      filter: "drop-shadow(0 0 28px rgba(117,255,154,0.34))",
    }}
  />
);

const Shot = ({ children }: { children: ReactNode }) => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill style={{ opacity: fadeOut(frame, shot), padding: "92px 72px 72px" }}>
      <Header />
      {children}
    </AbsoluteFill>
  );
};

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
          color: colors.neon,
          fontSize: 17,
          fontWeight: 950,
          letterSpacing: 0,
          textTransform: "uppercase",
          marginBottom: 18,
        }}
      >
        {eyebrow}
      </div>
      <div
        style={{
          fontSize: 56,
          lineHeight: 0.98,
          fontWeight: 950,
          letterSpacing: 0,
          marginBottom: 24,
        }}
      >
        {title}
      </div>
      <div style={{ color: colors.muted, fontSize: 25, lineHeight: 1.23, fontWeight: 650 }}>
        {body}
      </div>
    </div>
  );
};

const ShellFrame = ({
  file,
  title,
  scale = 1,
}: {
  file: string;
  title: string;
  scale?: number;
}) => {
  const frame = useCurrentFrame();
  const enter = ease(frame, 6, 24);
  return (
    <div
      style={{
        height: 762,
        borderRadius: 22,
        border: `1px solid ${colors.line}`,
        background: "rgba(2, 6, 4, 0.92)",
        boxShadow: "0 32px 120px rgba(0,0,0,0.52), 0 0 48px rgba(34,197,94,0.10)",
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
          borderBottom: "1px solid rgba(117,255,154,0.13)",
          background: "rgba(1, 5, 3, 0.98)",
        }}
      >
        <Logo size={32} />
        <span style={{ fontSize: 17, fontWeight: 950 }}>{title}</span>
        <span style={{ marginLeft: "auto", color: colors.neon, fontSize: 14, fontWeight: 900 }}>
          LIVE CAPTURE
        </span>
      </div>
      <Img
        src={staticFile(`current-ui/${file}`)}
        style={{ width: "100%", height: 706, objectFit: "contain", backgroundColor: "#020604" }}
      />
    </div>
  );
};

const Metric = ({ value, label, tone = colors.neon }: { value: string; label: string; tone?: string }) => {
  const frame = useCurrentFrame();
  const enter = ease(frame, 18, 24);
  return (
    <div
      style={{
        borderRadius: 20,
        border: `1px solid ${tone}66`,
        background: `${tone}18`,
        padding: "23px 24px",
        opacity: enter,
        transform: `translateY(${interpolate(enter, [0, 1], [18, 0])}px)`,
      }}
    >
      <div style={{ color: tone, fontSize: 45, fontWeight: 950, lineHeight: 1 }}>{value}</div>
      <div
        style={{
          color: colors.muted,
          fontSize: 15,
          fontWeight: 900,
          letterSpacing: 0,
          textTransform: "uppercase",
          marginTop: 10,
        }}
      >
        {label}
      </div>
    </div>
  );
};

const MiniShot = ({ file, label }: { file: string; label: string }) => {
  const frame = useCurrentFrame();
  const enter = ease(frame, 12, 26);
  return (
    <div
      style={{
        borderRadius: 18,
        border: `1px solid ${colors.line}`,
        background: colors.panel,
        padding: 12,
        opacity: enter,
        transform: `translateY(${interpolate(enter, [0, 1], [22, 0])}px)`,
        boxShadow: "0 24px 70px rgba(0,0,0,0.35)",
      }}
    >
      <Img
        src={staticFile(`current-ui/${file}`)}
        style={{ width: "100%", aspectRatio: "16 / 10", objectFit: "cover", borderRadius: 12 }}
      />
      <div
        style={{
          marginTop: 12,
          color: colors.ink,
          fontSize: 18,
          fontWeight: 900,
          textAlign: "center",
        }}
      >
        {label}
      </div>
    </div>
  );
};

const architectureNodes = [
  "React / Vite / WebGL UI",
  "PyQt WebEngine host",
  "QWebChannel bridge",
  "Shell Hub + NL Router",
  "Tool Gateway + Agents",
  "Memory, RAG, Voice, OS Drivers",
];

const ArchitectureMap = () => {
  const frame = useCurrentFrame();
  const enter = ease(frame, 12, 28);
  const nodeStyle: CSSProperties = {
    borderRadius: 18,
    border: `1px solid ${colors.line}`,
    background: "rgba(2, 9, 5, 0.82)",
    color: colors.ink,
    padding: "22px 24px",
    fontSize: 25,
    fontWeight: 900,
    boxShadow: "0 20px 70px rgba(0,0,0,0.34)",
  };
  return (
    <div
      style={{
        opacity: enter,
        transform: `translateX(${interpolate(enter, [0, 1], [30, 0])}px)`,
        display: "grid",
        gap: 16,
      }}
    >
      {architectureNodes.map((node, index) => (
        <div key={node} style={nodeStyle}>
          <span style={{ color: colors.neon, marginRight: 16 }}>{String(index + 1).padStart(2, "0")}</span>
          {node}
        </div>
      ))}
    </div>
  );
};

const Hero = () => {
  const frame = useCurrentFrame();
  const pulse = interpolate(Math.sin(frame / 18), [-1, 1], [0.97, 1.04]);
  return (
    <Shot>
      <div
        style={{
          height: "100%",
          display: "grid",
          gridTemplateColumns: "0.86fr 1.14fr",
          gap: 54,
          alignItems: "center",
        }}
      >
        <div>
          <div style={{ transform: `scale(${pulse})`, transformOrigin: "left center", marginBottom: 34 }}>
            <Logo size={132} />
          </div>
          <TextBlock
            eyebrow="Current real UI"
            title="Shell AI OS Controller"
            body="Captured from the running desktop app, not a mockup. This is the current Shell neural interface inside PyQt WebEngine."
          />
        </div>
        <ShellFrame file="dashboard.png" title="Dashboard" />
      </div>
    </Shot>
  );
};

const Dashboard = () => (
  <Shot>
    <div style={{ display: "grid", gridTemplateColumns: "1.24fr 0.76fr", gap: 42, alignItems: "center" }}>
      <ShellFrame file="dashboard.png" title="Dashboard / Transcript / Chart" />
      <TextBlock
        eyebrow="Main workspace"
        title="Telemetry, orb, transcript, and chart composer on one screen."
        body="The dashboard keeps the live control lane visible while text-originated prompts stay text-only."
      />
    </div>
  </Shot>
);

const Control = () => (
  <Shot>
    <div style={{ display: "grid", gridTemplateColumns: "0.76fr 1.24fr", gap: 42, alignItems: "center" }}>
      <div>
        <TextBlock
          eyebrow="Control center"
          title="Tools and agents are exposed through the actual UI."
          body="The captured Control tab shows the catalog surface users can operate from Shell, with guarded execution paths behind it."
        />
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 18, marginTop: 34 }}>
          <Metric value="485" label="visible entries" />
          <Metric value="40" label="agent cards" tone={colors.emerald} />
        </div>
      </div>
      <ShellFrame file="control.png" title="Control Center" />
    </div>
  </Shot>
);

const GallerySettings = () => (
  <Shot>
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 34, alignItems: "center" }}>
      <ShellFrame file="gallery.png" title="Gallery" scale={0.98} />
      <ShellFrame file="settings.png" title="Settings" scale={0.98} />
    </div>
  </Shot>
);

const WorkspaceTabs = () => (
  <Shot>
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 26, alignItems: "center" }}>
      <MiniShot file="apps.png" label="Apps" />
      <MiniShot file="notes.png" label="Notes" />
      <MiniShot file="phone.png" label="Phone" />
    </div>
  </Shot>
);

const Macros = () => (
  <Shot>
    <div style={{ display: "grid", gridTemplateColumns: "1.16fr 0.84fr", gap: 42, alignItems: "center" }}>
      <ShellFrame file="macros.png" title="Macros" />
      <TextBlock
        eyebrow="Automation surface"
        title="Macros, app actions, notes, phone, gallery, and settings share one visual system."
        body="The README media now follows the same screen hierarchy users see when they launch Shell."
      />
    </div>
  </Shot>
);

const Architecture = () => (
  <Shot>
    <div style={{ display: "grid", gridTemplateColumns: "0.88fr 1.12fr", gap: 42, alignItems: "center" }}>
      <div>
        <TextBlock
          eyebrow="Architecture"
          title="Repo page now describes the real current stack."
          body="React UI, PyQt WebEngine, QWebChannel, Shell Hub, NL routing, tools, agents, memory, RAG, voice, and OS drivers stay documented as the product architecture."
        />
      </div>
      <ArchitectureMap />
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
          eyebrow="Public repository"
          title="Docs, screenshots, and video now match the running Shell UI."
          body="The public README uses real captured PNG screenshots and this landscape demo is rendered from those captures."
        />
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 18, marginTop: 34 }}>
          <Metric value="real" label="UI captures" tone={colors.neon} />
          <Metric value="16:9" label="English video" />
          <Metric value="local" label="desktop-first" tone={colors.amber} />
        </div>
      </div>
      <ShellFrame file="dashboard.png" title="Shell Web UI" />
    </div>
  </Shot>
);

export const ShellCurrentUiLandscape = () => (
  <Stage>
    {[Hero, Dashboard, Control, GallerySettings, WorkspaceTabs, Macros, Architecture, Final].map(
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
