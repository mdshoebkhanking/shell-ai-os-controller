"""
Shell AI Orb — Clean 3D Particle Sphere.

Step 1: Fibonacci sphere → evenly-distributed points on a unit sphere.
Step 2: Loop through points, multiply by radius → sphere shape.
Step 3: Simple rotation using delta-X and delta-Y (Rx * Ry matrices).
Step 4: Spread outer particles outward when speaking.
"""

import math, random
from PyQt6.QtCore import QTimer, QRectF, Qt, QElapsedTimer, QPointF
from PyQt6.QtGui import QColor, QPainter, QPen, QRadialGradient
from PyQt6.QtWidgets import QWidget, QSizePolicy

_TAU = math.pi * 2


# ═══════════════════════════════════════════════════════════════
#  Step 1: Fibonacci Sphere — evenly distributed unit-sphere points
# ═══════════════════════════════════════════════════════════════

def _make_sphere(n=200):
    """Fibonacci sphere: evenly distributed points on a unit sphere.
    Returns list of (x, y, z) tuples on the unit sphere."""
    pts = []
    golden = (1 + math.sqrt(5)) / 2
    for i in range(n):
        # Latitude: acos maps [0,1] → [0, pi]
        theta = math.acos(1 - 2 * (i + 0.5) / n)
        # Longitude: golden-ratio spacing prevents clustering
        phi = _TAU * i / golden
        x = math.sin(theta) * math.cos(phi)
        y = math.sin(theta) * math.sin(phi)
        z = math.cos(theta)
        pts.append((x, y, z))
    return pts


# ═══════════════════════════════════════════════════════════════
#  Step 3: Simple Rotation — delta-X then delta-Y matrices
# ═══════════════════════════════════════════════════════════════

def _rotate(x, y, z, angle_x, angle_y):
    """Rotate a 3D point: first around X-axis, then around Y-axis."""
    # Rotation around X-axis
    cos_x, sin_x = math.cos(angle_x), math.sin(angle_x)
    y1 = y * cos_x - z * sin_x
    z1 = y * sin_x + z * cos_x

    # Rotation around Y-axis
    cos_y, sin_y = math.cos(angle_y), math.sin(angle_y)
    x1 = x * cos_y + z1 * sin_y
    z2 = -x * sin_y + z1 * cos_y

    return x1, y1, z2


class AIOrb(QWidget):
    """Clean 3D particle sphere with rotation and spread."""

    # Color themes per state
    THEMES = {
        "IDLE":      {"dot": (143, 245, 255), "glow": (0, 240, 255)},
        "LISTENING": {"dot": (100, 255, 220), "glow": (0, 255, 200)},
        "SPEAKING":  {"dot": (190, 150, 255), "glow": (172, 137, 255)},
        "THINKING":  {"dot": (255, 220, 100), "glow": (255, 200, 60)},
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background:transparent; border:none;")
        self._display_size = 280
        self.setMinimumSize(180, 180)
        self.setMaximumSize(500, 500)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # ── Step 1: Create sphere points ──
        self._pts = _make_sphere(200)
        self._sphere_radius = 90

        # ── Step 3: Rotation state — accumulated angles + delta speeds ──
        self._angle_x = 0.0
        self._angle_y = 0.0
        self._delta_x = 0.006      # rotation speed around X
        self._delta_y = 0.010      # rotation speed around Y

        # ── Step 4: Spread factor (0 = tight sphere, 1 = expanded) ──
        self._spread = 0.0
        self._target_spread = 0.0

        # Breathing pulse (subtle scale oscillation)
        self._pulse_phase = 0.0
        self._pulse_scale = 1.0

        # Voice/audio amplitude (smoothed)
        self._voice_amp = 0.0
        self._target_amp = 0.0

        # Current dot color (interpolated smoothly)
        theme = self.THEMES["IDLE"]
        self._color = list(theme["dot"])         # [R, G, B]
        self._glow_color = list(theme["glow"])   # [R, G, B]

        # State
        self.state = "IDLE"
        self.is_speaking = False
        self.is_listening = False
        self.is_thinking = False
        self.voice_intensity = 0.0
        self.audio_energy = 0.0
        self.target_audio_energy = 0.0

        # Compat fields (required by shell_cinematic_full)
        self.custom_status_text = ""
        self.status_text = ""
        self.dot_count = 100
        self.dot_open = 0.08
        self.user_merge = 0.0
        self._radius = 1.0
        self._cur_text = QColor(214, 201, 184, 200)

        # Animation timer (~60 FPS)
        self._elapsed = QElapsedTimer()
        self._elapsed.start()
        self._last_ns = self._elapsed.nsecsElapsed()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(16)

    def set_display_size(self, px: int):
        self._display_size = int(max(180, min(500, px)))
        self._sphere_radius = self._display_size * 0.32

    # ═══════════════════════════════════════════════════════════
    #  Public API
    # ═══════════════════════════════════════════════════════════

    def set_speaking(self, speaking: bool, intensity: float = 1.0):
        self.is_speaking = bool(speaking)
        self.voice_intensity = max(0.0, min(2.6, float(intensity)))
        self.state = "SPEAKING" if speaking else ("IDLE" if self.state == "SPEAKING" else self.state)
        self._sync_status()

    def set_listening_mode(self, listening: bool):
        self.is_listening = bool(listening)
        if listening:
            self.state = "LISTENING"
        elif self.state == "LISTENING":
            self.state = "IDLE"
        self._sync_status()

    def set_thinking(self, thinking: bool):
        self.is_thinking = bool(thinking)
        if thinking:
            self.state = "THINKING"
        elif self.state == "THINKING":
            self.state = "IDLE"
        self._sync_status()

    def trigger_user_speaking(self, strength: float = 1.0):
        strength = max(0.0, min(1.5, float(strength)))
        self._target_amp = max(self._target_amp, strength * 0.7)
        self.target_audio_energy = max(self.target_audio_energy, strength * 0.5)
        self.state = "LISTENING"
        self._sync_status()

    def set_energy(self, level: float):
        self.target_audio_energy = max(0.0, min(1.4, float(level)))
        self._target_amp = max(0.0, min(1.4, float(level)))

    def update_subtitle(self, text: str):
        self.custom_status_text = (text or "").strip()
        self.status_text = self.custom_status_text
        self.update()

    def set_mouse_focus(self, nx, ny):
        pass

    def _sync_status(self):
        m = {"SPEAKING": "VOICE ACTIVE", "LISTENING": "LISTENING", "THINKING": "PROCESSING"}
        self.status_text = m.get(self.state, self.custom_status_text)

    # ═══════════════════════════════════════════════════════════
    #  Animation Tick
    # ═══════════════════════════════════════════════════════════

    def _tick(self):
        now_ns = self._elapsed.nsecsElapsed()
        dt_ms = max(1.0, (now_ns - self._last_ns) / 1_000_000.0)
        self._last_ns = now_ns
        dt = min(3.0, dt_ms / 16.667)   # normalize to ~1.0 at 60fps

        # ── Smooth voice amplitude ──
        self._voice_amp += (self._target_amp - self._voice_amp) * 0.20 * dt
        self._target_amp *= (0.85 ** dt)
        if self._target_amp < 0.003:
            self._target_amp = 0.0

        self.audio_energy += (self.target_audio_energy - self.audio_energy) * 0.15 * dt
        self.target_audio_energy *= (0.88 ** dt)

        amp = max(self._voice_amp, self.audio_energy)

        # ── Step 3: Update rotation angles ──
        speed = 1.0
        if self.state == "THINKING":
            speed = 3.0
        elif self.state == "SPEAKING":
            speed = 1.5 + amp * 2.5
        elif amp > 0.1:
            speed = 1.0 + amp * 1.5

        self._angle_x += self._delta_x * dt * speed
        self._angle_y += self._delta_y * dt * speed

        # ── Step 4: Spread when speaking ──
        if self.is_speaking or amp > 0.15:
            self._target_spread = min(1.0, 0.15 + amp * 0.85)
        else:
            self._target_spread = 0.0
        self._spread += (self._target_spread - self._spread) * 0.10 * dt

        # ── Breathing pulse ──
        self._pulse_phase += 0.03 * dt
        peak = 1.02 + amp * 0.05
        self._pulse_scale = 1.0 + (peak - 1.0) * (0.5 + 0.5 * math.sin(self._pulse_phase))

        # ── Smooth color interpolation toward target theme ──
        target = self.THEMES.get(self.state, self.THEMES["IDLE"])
        lerp = 0.06 * dt
        for i in range(3):
            self._color[i] += (target["dot"][i] - self._color[i]) * lerp
            self._glow_color[i] += (target["glow"][i] - self._glow_color[i]) * lerp

        # Decay voice intensity when not speaking
        if not self.is_speaking:
            self.voice_intensity *= (0.93 ** dt)
            if self.voice_intensity < 0.02:
                self.voice_intensity = 0.0

        self.update()

    # ═══════════════════════════════════════════════════════════
    #  Paint — Project, sort, draw
    # ═══════════════════════════════════════════════════════════

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        cx = w / 2.0
        cy = h / 2.0

        amp = max(self._voice_amp, self.audio_energy)
        R = self._sphere_radius * self._pulse_scale

        # Spread multiplier for Step 4
        spread_mult = 1.0 + self._spread * 0.55

        # Extract colors as ints
        dr, dg, db = int(self._color[0]), int(self._color[1]), int(self._color[2])
        gr, gg, gb = int(self._glow_color[0]), int(self._glow_color[1]), int(self._glow_color[2])

        # Transparent background (integrates with glass UI)
        p.fillRect(self.rect(), QColor(0, 0, 0, 0))
        p.setPen(Qt.PenStyle.NoPen)

        # ── Single soft halo glow behind the sphere ──
        halo_r = R * 1.8 + amp * R * 0.3
        halo_alpha = int(min(30, 8 + amp * 20))
        halo = QRadialGradient(QPointF(cx, cy), halo_r)
        halo.setColorAt(0.0, QColor(gr, gg, gb, halo_alpha))
        halo.setColorAt(0.4, QColor(gr, gg, gb, int(halo_alpha * 0.3)))
        halo.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.setBrush(halo)
        p.drawEllipse(QRectF(cx - halo_r, cy - halo_r, halo_r * 2, halo_r * 2))

        # ═══════════════════════════════════════════════════════
        #  Step 2: Loop through points → sphere shape
        #  Step 3: Apply rotation (delta X/Y)
        #  Step 4: Apply spread for outer particles
        #  Then project 3D → 2D and sort by depth
        # ═══════════════════════════════════════════════════════

        projected = []
        for (ux, uy, uz) in self._pts:
            # Step 4: Spread — push particles outward from center
            sx = ux * spread_mult
            sy = uy * spread_mult
            sz = uz * spread_mult

            # Step 3: Rotate using accumulated delta-X and delta-Y
            rx, ry, rz = _rotate(sx, sy, sz, self._angle_x, self._angle_y)

            # Step 2: Scale unit-sphere point by radius → sphere shape
            screen_x = cx + rx * R
            screen_y = cy + ry * R
            # rz is depth: -1 (far/back) to +1 (near/front)

            projected.append((screen_x, screen_y, rz))

        # Painter's algorithm: sort by depth, draw back-to-front
        projected.sort(key=lambda pt: pt[2])

        # ── Draw each particle ──
        for screen_x, screen_y, depth in projected:
            # Normalized depth: 0.0 (back) → 1.0 (front)
            nd = (depth + 1.0) * 0.5

            # Particle size: small at back, large at front
            dot_size = 0.8 + nd * nd * 3.5 + amp * 0.3

            # Particle alpha: dim at back, bright at front
            alpha = int(max(8, nd * nd * nd * 255 + amp * 20))
            alpha = min(255, alpha)

            # Draw the dot
            p.setBrush(QColor(dr, dg, db, alpha))
            p.drawEllipse(QPointF(screen_x, screen_y), dot_size, dot_size)

        p.end()

    # Compat
    @staticmethod
    def _lerp_color(c, t, f):
        return c
