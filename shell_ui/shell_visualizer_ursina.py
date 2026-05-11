"""
Shell 3D Visualizer (Ursina + OpenGL Shaders) - Final Upgrade

Install:
    pip install ursina numpy psutil
    # Optional real-time FFT input:
    pip install pyaudio

Run:
    python shell_visualizer_ursina.py

Debug keys:
    Hold I -> USER_TALKING simulation
    Hold O -> SHELL_TALKING simulation
    Hold T -> THINKING simulation
    Hold E -> ERROR simulation
    Click near orb center -> Shockwave
"""

from __future__ import annotations

import argparse
import json
import math
import os
import socket
import threading
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional

import numpy as np

try:
    import psutil
except Exception:  # pragma: no cover - optional dependency
    psutil = None

try:
    import pyaudio
except Exception:  # pragma: no cover - optional dependency
    pyaudio = None

from ursina import (
    Entity,
    Mesh,
    Shader,
    Text,
    Ursina,
    Vec3,
    Vec4,
    camera,
    clamp,
    color,
    held_keys,
    lerp,
    mouse,
    time,
    window,
)


class VisualState(Enum):
    IDLE = "idle"
    USER_TALKING = "user_talking"
    SHELL_TALKING = "shell_talking"
    THINKING = "thinking"
    ERROR = "error"


@dataclass
class VisualConfig:
    particle_count: int = 10200
    radius: float = 2.2
    shell_thickness: float = 0.055

    # Smooth transition target: ~0.5s
    transition_duration: float = 0.5
    volume_smoothing: float = 10.0

    input_threshold: float = 0.03
    output_threshold: float = 0.03

    # Core colors
    idle_color: Vec3 = Vec3(1.0, 0.749, 0.0)      # #FFBF00
    user_color: Vec3 = Vec3(1.0, 0.64, 0.20)      # bright gold/orange
    shell_color: Vec3 = Vec3(0.0, 1.0, 1.0)       # #00FFFF
    thinking_color: Vec3 = Vec3(0.10, 0.88, 0.78) # cyan/teal
    error_color: Vec3 = Vec3(0.74, 0.06, 0.08)    # deep red

    # Interaction
    mouse_tilt_max_deg: float = 2.4
    click_radius_norm: float = 0.25
    shockwave_duration: float = 0.75
    shockwave_strength: float = 0.30


PARTICLE_SHADER = Shader(
    language=Shader.GLSL,
    vertex="""
#version 140
uniform mat4 p3d_ModelViewProjectionMatrix;
in vec4 p3d_Vertex;
in vec4 p3d_Color;

uniform float u_time;
uniform vec4 u_state_mix_a; // x=idle,y=user,z=shell,w=thinking
uniform float u_error_mix;

uniform float u_input_amp;
uniform float u_output_amp;
uniform float u_bass_amp;
uniform float u_treble_amp;

uniform float u_shock_strength; // 0..1
uniform float u_shock_phase;    // 0..1

uniform float u_battery_dim; // for gold dim/flicker

uniform vec3 u_idle_color;
uniform vec3 u_user_color;
uniform vec3 u_shell_color;
uniform vec3 u_thinking_color;
uniform vec3 u_error_color;

out vec4 v_color;

float hash(float n) {
    return fract(sin(n) * 43758.5453123);
}

void main() {
    vec3 p = p3d_Vertex.xyz;
    float seed = p3d_Color.r * 17.0 + p3d_Color.g * 31.0 + p3d_Color.b * 47.0;
    float sparkle = hash(seed * 13.1 + 0.77);
    float idle_w = u_state_mix_a.x;
    float user_w = u_state_mix_a.y;
    float shell_w = u_state_mix_a.z;
    float think_w = u_state_mix_a.w;
    float err_w = u_error_mix;

    // IDLE breathing
    float breathe = 1.0 + sin(u_time * 0.85 + seed * 3.7) * 0.012 * (0.4 + idle_w);
    p *= breathe;

    // USER_TALKING jitter/vibration
    float user_jitter = (0.01 + u_input_amp * 0.09 + u_bass_amp * 0.03) * user_w;
    p += vec3(
        sin(u_time * 23.0 + seed * 6.2),
        cos(u_time * 21.0 + seed * 5.1),
        sin(u_time * 26.0 + seed * 4.4)
    ) * user_jitter;

    // SHELL_TALKING concentric flow (fast spin)
    float shell_flow = (0.9 + u_output_amp * 3.4 + u_treble_amp * 1.2) * shell_w;
    float a_shell = shell_flow * u_time + seed * 6.2831853;
    mat2 r_shell = mat2(cos(a_shell), -sin(a_shell), sin(a_shell), cos(a_shell));
    p.xz = mix(p.xz, r_shell * p.xz, shell_w);
    p.y += sin(a_shell * 2.0 + u_time * 6.0) * 0.022 * shell_w;

    // THINKING vortex (spiral-in toward center)
    if (think_w > 0.001) {
        float r = length(p.xz);
        float ang = atan(p.z, p.x);
        float vortex_speed = 2.2 + u_treble_amp * 2.8;
        ang += vortex_speed * u_time * think_w + seed * 0.42;
        float inward = (0.05 + 0.06 * (0.5 + 0.5 * sin(u_time * 2.0 + seed))) * think_w;
        r = max(0.04, r - inward);
        p.x = cos(ang) * r;
        p.z = sin(ang) * r;
        p.y *= (1.0 - 0.10 * think_w);
    }

    // ERROR glitch/shake distortion
    if (err_w > 0.001) {
        float gx = sin(u_time * 82.0 + seed * 33.0) * 0.04 * err_w;
        float gy = cos(u_time * 97.0 + seed * 27.0) * 0.025 * err_w;
        float gz = sin(u_time * 108.0 + seed * 41.0) * 0.04 * err_w;
        p += vec3(gx, gy, gz);
    }

    // Shockwave on click: spread outward then return.
    float shock_curve = sin(u_shock_phase * 3.1415926) * u_shock_strength;
    vec3 n = normalize(p + vec3(1e-5));
    p += n * shock_curve * (0.6 + sparkle * 0.7);

    gl_Position = p3d_ModelViewProjectionMatrix * vec4(p, 1.0);

    // FFT-reactive point size + state contributions
    float size = 1.00 + sparkle * 1.05;
    size += user_w * (0.28 + u_input_amp * 1.9 + u_bass_amp * 0.7);
    size += shell_w * (0.20 + u_output_amp * 1.55 + u_treble_amp * 0.9);
    size += think_w * (0.20 + u_treble_amp * 0.45);
    size += err_w * 0.45;
    gl_PointSize = clamp(size, 0.85, 4.1);

    vec3 state_color = u_idle_color * idle_w
                     + u_user_color * user_w
                     + u_shell_color * shell_w
                     + u_thinking_color * think_w
                     + u_error_color * err_w;

    // Battery dim/flicker only for gold states (idle + user)
    float gold_mix = clamp(idle_w + user_w, 0.0, 1.0);
    state_color = mix(state_color, state_color * u_battery_dim, gold_mix);
    state_color *= (0.80 + sparkle * 0.34);

    v_color = vec4(state_color, p3d_Color.a);
}
""",
    fragment="""
#version 140
in vec4 v_color;
out vec4 fragColor;

void main() {
    // Soft circular point with bloom-ish falloff.
    vec2 uv = gl_PointCoord * 2.0 - vec2(1.0);
    float d = dot(uv, uv);
    if (d > 1.0) discard;

    float core = pow(max(0.0, 1.0 - d), 2.1);
    float halo = pow(max(0.0, 1.0 - d), 0.8) * 0.55;

    vec3 rgb = v_color.rgb * (0.78 + core * 0.82 + halo * 0.35);
    float a = v_color.a * (core + halo * 0.35);
    fragColor = vec4(rgb, a);
}
""",
)


BACKGROUND_SHADER = Shader(
    language=Shader.GLSL,
    vertex="""
#version 140
uniform mat4 p3d_ModelViewProjectionMatrix;
in vec4 p3d_Vertex;
in vec2 p3d_MultiTexCoord0;
out vec2 uv;

void main() {
    gl_Position = p3d_ModelViewProjectionMatrix * p3d_Vertex;
    uv = p3d_MultiTexCoord0;
}
""",
    fragment="""
#version 140
in vec2 uv;
out vec4 fragColor;

uniform float u_aspect;
uniform float u_time;
uniform float u_orb_glow;

float hash(vec2 p) {
    return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453123);
}

float noise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    vec2 u = f * f * (3.0 - 2.0 * f);
    return mix(
        mix(hash(i + vec2(0.0, 0.0)), hash(i + vec2(1.0, 0.0)), u.x),
        mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), u.x),
        u.y
    );
}

void main() {
    // Deep chocolate-black gradient
    vec3 edge = vec3(0.028, 0.020, 0.015);
    vec3 base = vec3(0.102, 0.082, 0.063); // #1a1510
    vec3 center_glow = vec3(0.24, 0.15, 0.07);

    vec2 p = uv - vec2(0.5, 0.42);
    p.x *= u_aspect;
    float dist = length(p * vec2(1.0, 1.2));

    float radial = smoothstep(0.95, 0.0, dist);
    vec3 c = mix(edge, base, 0.62);
    c = mix(c, center_glow, radial * (0.35 + u_orb_glow * 0.45));

    // Subtle dust/fog responding to orb glow
    float n1 = noise(uv * vec2(190.0, 115.0) + vec2(u_time * 0.11, -u_time * 0.07));
    float n2 = noise(uv * vec2(280.0, 170.0) - vec2(u_time * 0.08, u_time * 0.05));
    float dust = (n1 * 0.65 + n2 * 0.35);
    float fog = smoothstep(0.55, 1.0, dust) * (0.035 + u_orb_glow * 0.025);
    c += vec3(0.22, 0.17, 0.11) * fog;

    fragColor = vec4(c, 1.0);
}
""",
)


def get_battery_percentage() -> Optional[float]:
    """
    Battery monitor helper.
    Returns:
        float percent (0..100) if available, else None.
    """
    if psutil is None:
        return None
    try:
        bat = psutil.sensors_battery()
        if bat is None:
            return None
        return float(bat.percent)
    except Exception:
        return None


class AudioSpectrumAnalyzer:
    """
    Real-time audio FFT boilerplate (PyAudio).
    Integration use:
        analyzer.start()
        bass, treble, level = analyzer.read_spectrum()
    """

    def __init__(self, sample_rate: int = 16000, chunk_size: int = 1024):
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.enabled = pyaudio is not None
        self._pya = None
        self._stream = None
        self._last_buffer = np.zeros(chunk_size, dtype=np.float32)
        self._lock = threading.Lock()

    def start(self) -> None:
        if not self.enabled:
            return
        try:
            self._pya = pyaudio.PyAudio()
            self._stream = self._pya.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.sample_rate,
                input=True,
                frames_per_buffer=self.chunk_size,
                stream_callback=self._callback,
            )
            self._stream.start_stream()
        except Exception:
            self.enabled = False
            self.stop()

    def stop(self) -> None:
        try:
            if self._stream is not None:
                self._stream.stop_stream()
                self._stream.close()
        except Exception:
            pass
        try:
            if self._pya is not None:
                self._pya.terminate()
        except Exception:
            pass
        self._stream = None
        self._pya = None

    def _callback(self, in_data, frame_count, time_info, status):
        data = np.frombuffer(in_data, dtype=np.int16).astype(np.float32)
        data /= 32768.0
        with self._lock:
            if len(data) >= self.chunk_size:
                self._last_buffer = data[: self.chunk_size].copy()
            else:
                self._last_buffer[: len(data)] = data
        return (None, pyaudio.paContinue)

    def read_spectrum(self) -> tuple[float, float, float]:
        """
        Returns:
            bass_amp, treble_amp, level (all normalized 0..1)
        """
        with self._lock:
            x = self._last_buffer.copy()

        if np.max(np.abs(x)) < 1e-6:
            return 0.0, 0.0, 0.0

        window_fn = np.hanning(len(x)).astype(np.float32)
        fft = np.fft.rfft(x * window_fn)
        mag = np.abs(fft).astype(np.float32)
        freqs = np.fft.rfftfreq(len(x), 1.0 / self.sample_rate).astype(np.float32)

        bass_band = mag[(freqs >= 20.0) & (freqs <= 250.0)]
        treble_band = mag[(freqs >= 2500.0) & (freqs <= 8000.0)]
        level = float(np.sqrt(np.mean(x * x)))

        bass = float(np.mean(bass_band)) if len(bass_band) else 0.0
        treble = float(np.mean(treble_band)) if len(treble_band) else 0.0

        # Soft normalization (log-ish) to keep stable.
        bass_n = clamp(math.log1p(bass * 50.0) / 4.0, 0.0, 1.0)
        treble_n = clamp(math.log1p(treble * 50.0) / 4.0, 0.0, 1.0)
        level_n = clamp(level * 7.0, 0.0, 1.0)
        return bass_n, treble_n, level_n


class OrbCommandListener:
    """Non-blocking UDP command listener for external UI integration."""

    def __init__(self, port: Optional[int]):
        self.port = int(port or 0)
        self._sock: Optional[socket.socket] = None

    def start(self) -> bool:
        if self.port <= 0:
            return False
        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._sock.bind(("127.0.0.1", self.port))
            self._sock.setblocking(False)
            return True
        except Exception:
            self.stop()
            return False

    def poll(self) -> Optional[Dict]:
        if self._sock is None:
            return None
        latest: Optional[Dict] = None
        while True:
            try:
                payload, _ = self._sock.recvfrom(8192)
            except BlockingIOError:
                break
            except Exception:
                break
            try:
                data = json.loads(payload.decode("utf-8", errors="ignore"))
            except Exception:
                continue
            if isinstance(data, dict):
                latest = data
        return latest

    def stop(self) -> None:
        try:
            if self._sock is not None:
                self._sock.close()
        except Exception:
            pass
        self._sock = None


def generate_shell_points(
    count: int,
    radius: float,
    thickness: float,
    seed: int = 11,
) -> np.ndarray:
    """Fast near-uniform sphere shell points using NumPy + spherical math."""
    rng = np.random.default_rng(seed)
    i = np.arange(count, dtype=np.float32)
    golden = (1.0 + 5.0**0.5) * 0.5
    theta = (2.0 * math.pi * i / golden).astype(np.float32)
    v = (i + 0.5) / float(count)
    phi = np.arccos(1.0 - 2.0 * v).astype(np.float32)
    r = radius + rng.uniform(-thickness, thickness, size=count).astype(np.float32)
    x = r * np.sin(phi) * np.cos(theta)
    y = r * np.cos(phi)
    z = r * np.sin(phi) * np.sin(theta)
    return np.column_stack((x, y, z)).astype(np.float32)


def build_particle_mesh(config: VisualConfig) -> Mesh:
    count = max(10000, int(config.particle_count))
    points = generate_shell_points(count, config.radius, config.shell_thickness)
    rng = np.random.default_rng(77)
    seeds = rng.random((count, 3)).astype(np.float32)
    alpha = rng.uniform(0.62, 1.0, size=count).astype(np.float32)

    vertices = [Vec3(float(x), float(y), float(z)) for x, y, z in points]
    colors = [
        Vec4(float(seeds[i, 0]), float(seeds[i, 1]), float(seeds[i, 2]), float(alpha[i]))
        for i in range(count)
    ]
    return Mesh(vertices=vertices, colors=colors, mode="point", static=True)


class ShellVisualizer(Entity):
    """
    Final visualizer architecture.

    Integration-ready placeholders:
        self.input_volume  # set mic RMS (0..1)
        self.output_volume # set TTS/output RMS (0..1)
    """

    def __init__(
        self,
        config: Optional[VisualConfig] = None,
        debug_simulation: bool = True,
        auto_state: bool = True,
        use_audio_fft: bool = False,
        command_port: Optional[int] = None,
    ):
        super().__init__()
        self.config = config or VisualConfig()
        self.debug_simulation = debug_simulation
        self.auto_state = auto_state

        # State engine
        self.state = VisualState.IDLE
        self.target_state = VisualState.IDLE
        self.state_mix = np.array([1.0, 0.0, 0.0, 0.0, 0.0], dtype=np.float32)

        # Timing and input
        self.elapsed = 0.0
        self.input_volume = 0.0
        self.output_volume = 0.0
        self.input_smooth = 0.0
        self.output_smooth = 0.0
        self.bass_amp = 0.0
        self.treble_amp = 0.0

        # Flags
        self.error_active = False
        self.thinking_active = False

        # Shockwave
        self.shockwave_t = -1.0

        # Mouse interaction
        self._left_mouse_prev = False
        self.mouse_tilt_x = 0.0
        self.mouse_tilt_y = 0.0
        self.base_rotation_x = 0.0
        self.base_rotation_y = 0.0

        # Battery management
        self.battery_percent = get_battery_percentage()
        self.battery_dim = 1.0
        self._battery_timer = 0.0

        # Optional audio FFT
        self.audio_analyzer = AudioSpectrumAnalyzer()
        self.use_audio_fft = use_audio_fft and self.audio_analyzer.enabled
        if self.use_audio_fft:
            self.audio_analyzer.start()

        # Optional external commands from PyQt UI (local UDP JSON)
        self.command_listener = OrbCommandListener(command_port)
        self.command_listener_active = self.command_listener.start()
        self.subtitle = ""

        # Background (shader)
        self.bg = Entity(
            parent=camera,
            model="quad",
            shader=BACKGROUND_SHADER,
            unlit=True,
            double_sided=True,
            position=(0, 0, 42),
            scale=(92, 52),
        )
        self.bg.set_shader_input("u_aspect", window.aspect_ratio)
        self.bg.set_shader_input("u_time", 0.0)
        self.bg.set_shader_input("u_orb_glow", 0.35)

        # Orb
        self.orb = Entity(
            model=build_particle_mesh(self.config),
            shader=PARTICLE_SHADER,
            unlit=True,
            position=(0, 0, 0),
            scale=1.0,
        )
        self._push_shader_inputs()

        # HUD
        self.status_text = Text(
            text="STATE: IDLE",
            position=(0, -0.46),
            origin=(0, 0),
            color=color.rgba(230, 210, 185, 190),
            scale=1.05,
            background=False,
        )
        self.hint_text = Text(
            text="I:user  O:shell  T:thinking  E:error  Click:shockwave",
            position=(0, -0.495),
            origin=(0, 0),
            color=color.rgba(160, 160, 160, 145),
            scale=0.86,
            background=False,
        )

    # ---------- Public integration API ----------
    def set_input_volume(self, value: float) -> None:
        self.input_volume = clamp(value, 0.0, 1.0)

    def set_output_volume(self, value: float) -> None:
        self.output_volume = clamp(value, 0.0, 1.0)

    def set_state(self, state: VisualState) -> None:
        self.target_state = state

    def set_thinking(self, active: bool) -> None:
        self.thinking_active = bool(active)

    def set_error(self, active: bool) -> None:
        self.error_active = bool(active)

    def _to_float(self, value, default: float = 0.0) -> float:
        try:
            return float(value)
        except Exception:
            return default

    def _apply_external_command(self, cmd: Dict) -> None:
        raw_state = str(cmd.get("state", "")).strip().lower()
        mapping: Dict[str, VisualState] = {
            "idle": VisualState.IDLE,
            "user": VisualState.USER_TALKING,
            "user_talking": VisualState.USER_TALKING,
            "shell": VisualState.SHELL_TALKING,
            "shell_talking": VisualState.SHELL_TALKING,
            "thinking": VisualState.THINKING,
            "error": VisualState.ERROR,
        }
        if raw_state in mapping:
            self.set_state(mapping[raw_state])

        if "input_volume" in cmd:
            self.set_input_volume(self._to_float(cmd.get("input_volume"), self.input_volume))
        if "output_volume" in cmd:
            self.set_output_volume(self._to_float(cmd.get("output_volume"), self.output_volume))

        if "thinking" in cmd:
            self.set_thinking(bool(cmd.get("thinking")))
        if "error" in cmd:
            self.set_error(bool(cmd.get("error")))

        if bool(cmd.get("shockwave")):
            self.shockwave_t = 0.0

        subtitle = str(cmd.get("subtitle", "")).strip()
        if subtitle:
            self.subtitle = subtitle[:90]

    # ---------- Internal systems ----------
    def _target_mix(self) -> np.ndarray:
        mapping: Dict[VisualState, np.ndarray] = {
            VisualState.IDLE: np.array([1.0, 0.0, 0.0, 0.0, 0.0], dtype=np.float32),
            VisualState.USER_TALKING: np.array([0.0, 1.0, 0.0, 0.0, 0.0], dtype=np.float32),
            VisualState.SHELL_TALKING: np.array([0.0, 0.0, 1.0, 0.0, 0.0], dtype=np.float32),
            VisualState.THINKING: np.array([0.0, 0.0, 0.0, 1.0, 0.0], dtype=np.float32),
            VisualState.ERROR: np.array([0.0, 0.0, 0.0, 0.0, 1.0], dtype=np.float32),
        }
        return mapping[self.target_state]

    def _auto_resolve_state(self) -> VisualState:
        if self.error_active:
            return VisualState.ERROR
        if self.output_smooth > self.config.output_threshold:
            return VisualState.SHELL_TALKING
        if self.input_smooth > self.config.input_threshold:
            return VisualState.USER_TALKING
        if self.thinking_active:
            return VisualState.THINKING
        return VisualState.IDLE

    def _simulate_debug_input(self, dt: float) -> None:
        if held_keys["o"]:
            self.output_volume = clamp(self.output_volume + dt * 3.2, 0.0, 1.0)
        else:
            self.output_volume = max(0.0, self.output_volume - dt * 2.2)

        if held_keys["i"]:
            self.input_volume = clamp(self.input_volume + dt * 3.2, 0.0, 1.0)
        else:
            self.input_volume = max(0.0, self.input_volume - dt * 2.1)

        self.thinking_active = bool(held_keys["t"])
        self.error_active = bool(held_keys["e"])

    def _update_battery_effect(self, dt: float) -> None:
        self._battery_timer += dt
        if self._battery_timer >= 2.0:
            self._battery_timer = 0.0
            self.battery_percent = get_battery_percentage()

        if self.battery_percent is not None and self.battery_percent < 20.0:
            flicker = 0.84 + abs(math.sin(self.elapsed * 16.0)) * 0.16
            self.battery_dim = flicker
        else:
            self.battery_dim = lerp(self.battery_dim, 1.0, min(1.0, dt * 3.0))

    def _check_click_shockwave(self) -> None:
        left_now = bool(held_keys["left mouse"])
        if left_now and not self._left_mouse_prev:
            d = math.sqrt(float(mouse.x) * float(mouse.x) + float(mouse.y) * float(mouse.y))
            if d <= self.config.click_radius_norm:
                self.shockwave_t = 0.0
        self._left_mouse_prev = left_now

    def _update_shockwave(self, dt: float) -> tuple[float, float]:
        if self.shockwave_t < 0.0:
            return 0.0, 0.0
        self.shockwave_t += dt
        p = clamp(self.shockwave_t / self.config.shockwave_duration, 0.0, 1.0)
        strength = self.config.shockwave_strength * (1.0 - p * 0.15)
        if p >= 1.0:
            self.shockwave_t = -1.0
            return 0.0, 0.0
        return strength, p

    def _update_mouse_tilt(self, dt: float) -> None:
        target_x = clamp(-float(mouse.y) * self.config.mouse_tilt_max_deg, -self.config.mouse_tilt_max_deg, self.config.mouse_tilt_max_deg)
        target_y = clamp(float(mouse.x) * self.config.mouse_tilt_max_deg, -self.config.mouse_tilt_max_deg, self.config.mouse_tilt_max_deg)
        # Keep mouse influence very subtle.
        target_x *= 0.55
        target_y *= 0.55
        s = min(1.0, dt * 2.2)
        self.mouse_tilt_x = lerp(self.mouse_tilt_x, target_x, s)
        self.mouse_tilt_y = lerp(self.mouse_tilt_y, target_y, s)

    def _update_transform(self, dt: float) -> None:
        idle_w, user_w, shell_w, think_w, err_w = self.state_mix.tolist()

        # Base orbital rotation
        y_speed = (
            5.5 * idle_w
            + (16.0 + self.input_smooth * 30.0 + self.bass_amp * 15.0) * user_w
            + (35.0 + self.output_smooth * 58.0 + self.treble_amp * 20.0) * shell_w
            + (48.0 + self.treble_amp * 30.0) * think_w
            + 18.0 * err_w
        )
        x_speed = (
            2.0 * idle_w
            + (7.5 + self.input_smooth * 12.0) * user_w
            + (12.0 + self.output_smooth * 18.0) * shell_w
            + (7.0 + self.treble_amp * 12.0) * think_w
            + 10.0 * err_w
        )

        self.base_rotation_y += y_speed * dt
        self.base_rotation_x += x_speed * dt

        # Mouse tilt: apply as small offset, do not accumulate every frame.
        self.orb.rotation_x = self.base_rotation_x + self.mouse_tilt_x
        self.orb.rotation_y = self.base_rotation_y + self.mouse_tilt_y

        # Scale profiles
        idle_scale = 1.0 + math.sin(self.elapsed * 1.0) * 0.025
        user_scale = 1.02 + self.input_smooth * 0.18 + abs(math.sin(self.elapsed * 8.0)) * (0.03 + self.input_smooth * 0.06)
        shell_scale = (0.75 + self.output_smooth * 0.04) * (1.0 + math.sin(self.elapsed * 10.0) * (0.02 + self.output_smooth * 0.05))
        think_scale = 0.90 + math.sin(self.elapsed * 6.2) * 0.04
        error_scale = 1.02 + abs(math.sin(self.elapsed * 28.0)) * 0.08
        target_scale = idle_w * idle_scale + user_w * user_scale + shell_w * shell_scale + think_w * think_scale + err_w * error_scale
        self.orb.scale = lerp(self.orb.scale, Vec3(target_scale, target_scale, target_scale), min(1.0, dt * 6.5))

        # Position/bounce/shake
        bounce_amp = (0.08 + self.input_smooth * 0.30) * user_w
        bounce = math.sin(self.elapsed * (7.0 + self.input_smooth * 5.0)) * bounce_amp
        vib = (0.004 + self.input_smooth * 0.03 + self.bass_amp * 0.015) * user_w
        jitter_x = math.sin(self.elapsed * 32.0) * vib
        jitter_z = math.cos(self.elapsed * 29.0) * vib

        think_float = math.sin(self.elapsed * 6.0) * 0.025 * think_w
        shell_float = math.sin(self.elapsed * 4.2) * 0.016 * shell_w
        idle_float = math.sin(self.elapsed * 0.9) * 0.02 * idle_w

        err_shake = (0.012 + abs(math.sin(self.elapsed * 48.0)) * 0.055) * err_w
        err_x = math.sin(self.elapsed * 90.0) * err_shake
        err_y = math.cos(self.elapsed * 84.0) * err_shake * 0.7
        err_z = math.sin(self.elapsed * 96.0) * err_shake

        self.orb.position = Vec3(
            jitter_x + err_x,
            idle_float + bounce + shell_float + think_float + err_y,
            jitter_z + err_z,
        )

    def _push_shader_inputs(self, shock_strength: float = 0.0, shock_phase: float = 0.0) -> None:
        idle_w, user_w, shell_w, think_w, err_w = self.state_mix.tolist()
        self.orb.set_shader_input("u_time", self.elapsed)
        self.orb.set_shader_input("u_state_mix_a", Vec4(idle_w, user_w, shell_w, think_w))
        self.orb.set_shader_input("u_error_mix", float(err_w))
        self.orb.set_shader_input("u_input_amp", float(self.input_smooth))
        self.orb.set_shader_input("u_output_amp", float(self.output_smooth))
        self.orb.set_shader_input("u_bass_amp", float(self.bass_amp))
        self.orb.set_shader_input("u_treble_amp", float(self.treble_amp))
        self.orb.set_shader_input("u_shock_strength", float(shock_strength))
        self.orb.set_shader_input("u_shock_phase", float(shock_phase))
        self.orb.set_shader_input("u_battery_dim", float(self.battery_dim))

        self.orb.set_shader_input("u_idle_color", self.config.idle_color)
        self.orb.set_shader_input("u_user_color", self.config.user_color)
        self.orb.set_shader_input("u_shell_color", self.config.shell_color)
        self.orb.set_shader_input("u_thinking_color", self.config.thinking_color)
        self.orb.set_shader_input("u_error_color", self.config.error_color)

        glow_strength = clamp(
            idle_w * 0.35 + user_w * 0.55 + shell_w * 0.78 + think_w * 0.70 + err_w * 0.46,
            0.2,
            1.0,
        )
        self.bg.set_shader_input("u_aspect", window.aspect_ratio)
        self.bg.set_shader_input("u_time", self.elapsed)
        self.bg.set_shader_input("u_orb_glow", float(glow_strength))

    # ---------- Frame loop ----------
    def update(self) -> None:
        dt = time.dt
        self.elapsed += dt

        if self.command_listener_active:
            cmd = self.command_listener.poll()
            if cmd:
                self._apply_external_command(cmd)

        if self.debug_simulation:
            self._simulate_debug_input(dt)

        if self.use_audio_fft:
            bass, treble, level = self.audio_analyzer.read_spectrum()
            self.bass_amp = bass
            self.treble_amp = treble
            # Integration-ready values remain assignable externally too.
            self.input_volume = max(self.input_volume, level)
        else:
            # Lightweight synthetic fallback values
            self.bass_amp = lerp(self.bass_amp, self.input_volume * 0.7, min(1.0, dt * 4.0))
            self.treble_amp = lerp(self.treble_amp, self.output_volume * 0.7, min(1.0, dt * 4.0))

        # Smooth envelopes
        smooth_t = min(1.0, dt * self.config.volume_smoothing)
        self.input_smooth = lerp(self.input_smooth, clamp(self.input_volume, 0.0, 1.0), smooth_t)
        self.output_smooth = lerp(self.output_smooth, clamp(self.output_volume, 0.0, 1.0), smooth_t)

        # Resolve state
        if self.auto_state:
            self.target_state = self._auto_resolve_state()
        self.state = self.target_state

        # 0.5s smooth transition between states
        mix_t = min(1.0, dt / max(self.config.transition_duration, 1e-4))
        self.state_mix = self.state_mix + (self._target_mix() - self.state_mix) * mix_t

        self._check_click_shockwave()
        shock_strength, shock_phase = self._update_shockwave(dt)
        self._update_mouse_tilt(dt)
        self._update_battery_effect(dt)
        self._update_transform(dt)
        self._push_shader_inputs(shock_strength=shock_strength, shock_phase=shock_phase)

        subtitle = f" | {self.subtitle}" if self.subtitle else ""
        self.status_text.text = (
            f"STATE: {self.state.value.upper()} | "
            f"in={self.input_smooth:.2f} out={self.output_smooth:.2f} "
            f"bass={self.bass_amp:.2f} treble={self.treble_amp:.2f} "
            f"bat={self.battery_percent if self.battery_percent is not None else '--'}"
            f"{subtitle}"
        )

    def on_destroy(self) -> None:
        if self.use_audio_fft:
            self.audio_analyzer.stop()
        if self.command_listener_active:
            self.command_listener.stop()


def main() -> None:
    parser = argparse.ArgumentParser(description="Shell Ursina Visualizer")
    parser.add_argument("--title", type=str, default=os.environ.get("SHELL_URSINA_WINDOW_TITLE", "Shell OS 1.0.0 Visualizer"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("SHELL_URSINA_COMMAND_PORT", "0") or "0"))
    parser.add_argument("--parent-hwnd", type=int, default=0, help="Windows parent HWND for embedded mode.")
    parser.add_argument("--particles", type=int, default=10200)
    parser.add_argument("--fft", action="store_true", help="Enable microphone FFT (requires PyAudio).")
    parser.add_argument("--no-debug", action="store_true", help="Disable keyboard debug simulation.")
    parser.add_argument("--no-auto-state", action="store_true", help="Disable automatic state resolve.")
    parser.add_argument("--borderless", action="store_true", help="Launch Ursina window borderless.")
    args = parser.parse_args()

    if int(args.parent_hwnd) > 0:
        try:
            from panda3d.core import loadPrcFileData
            loadPrcFileData("", f"parent-window-handle {int(args.parent_hwnd)}")
            loadPrcFileData("", "undecorated 1")
            loadPrcFileData("", "win-origin 0 0")
            loadPrcFileData("", "show-frame-rate-meter 0")
        except Exception:
            pass

    app = Ursina(borderless=(args.borderless or int(args.parent_hwnd) > 0), development_mode=False)
    window.title = args.title
    window.color = color.black
    window.exit_button.visible = False
    window.fps_counter.enabled = True

    camera.position = Vec3(0, 0, -7.35)
    camera.fov = 48

    ShellVisualizer(
        config=VisualConfig(particle_count=max(10000, int(args.particles))),
        debug_simulation=not args.no_debug,
        auto_state=not args.no_auto_state,
        use_audio_fft=bool(args.fft),
        command_port=(args.port if args.port > 0 else None),
    )
    app.run()


if __name__ == "__main__":
    main()
