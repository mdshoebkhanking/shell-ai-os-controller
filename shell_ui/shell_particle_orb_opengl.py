"""
Shell 3D Particle Orb (High Performance)

Install:
    pip install numpy pygame PyOpenGL PyOpenGL_accelerate

Run:
    python shell_particle_orb_opengl.py --particles 6800
"""

from __future__ import annotations

import argparse
import math
import sys

import numpy as np
import pygame
from OpenGL.GL import (
    GL_ARRAY_BUFFER,
    GL_BLEND,
    GL_COLOR_ARRAY,
    GL_COLOR_BUFFER_BIT,
    GL_DEPTH_BUFFER_BIT,
    GL_DEPTH_TEST,
    GL_FLOAT,
    GL_LEQUAL,
    GL_MODELVIEW,
    GL_ONE,
    GL_ONE_MINUS_SRC_ALPHA,
    GL_POINTS,
    GL_POINT_SMOOTH,
    GL_POINT_SMOOTH_HINT,
    GL_PROJECTION,
    GL_QUADS,
    GL_SRC_ALPHA,
    GL_STATIC_DRAW,
    GL_TRIANGLE_FAN,
    GL_VERTEX_ARRAY,
    GL_NICEST,
    glBegin,
    glBindBuffer,
    glBlendFunc,
    glBufferData,
    glClear,
    glClearColor,
    glColor4f,
    glColorPointer,
    glDepthFunc,
    glDisable,
    glDisableClientState,
    glDrawArrays,
    glEnable,
    glEnableClientState,
    glEnd,
    glGenBuffers,
    glHint,
    glLoadIdentity,
    glMatrixMode,
    glOrtho,
    glPointSize,
    glPopMatrix,
    glPushMatrix,
    glRotatef,
    glTranslatef,
    glVertex2f,
    glVertexPointer,
    glViewport,
)
from OpenGL.GLU import gluPerspective


def hex_to_rgb01(hex_color: str) -> tuple[float, float, float]:
    """Convert #RRGGBB to normalized float RGB."""
    h = hex_color.lstrip("#")
    return (int(h[0:2], 16) / 255.0, int(h[2:4], 16) / 255.0, int(h[4:6], 16) / 255.0)


def build_sphere_shell_positions(
    count: int,
    radius: float = 2.15,
    shell_thickness: float = 0.035,
) -> np.ndarray:
    """
    Generate hollow sphere points using spherical coordinates.

    cos(theta) is sampled uniformly in [-1, 1] for even distribution.
    phi is sampled uniformly in [0, 2*pi].
    """
    phi = np.random.uniform(0.0, 2.0 * math.pi, count).astype(np.float32)
    cos_theta = np.random.uniform(-1.0, 1.0, count).astype(np.float32)
    sin_theta = np.sqrt(1.0 - np.square(cos_theta)).astype(np.float32)

    # Very thin shell around radius to keep orb hollow.
    jitter = np.random.normal(0.0, shell_thickness, count).astype(np.float32)
    r = np.clip(radius + jitter, radius - shell_thickness * 2.0, radius + shell_thickness * 2.0)

    x = r * sin_theta * np.cos(phi)
    y = r * cos_theta
    z = r * sin_theta * np.sin(phi)

    return np.column_stack((x, y, z)).astype(np.float32)


def build_particle_colors(count: int) -> np.ndarray:
    """
    Build cinematic palette:
    - Amber: #FFBF00
    - Gold: #FFD700
    - Warm White mix for sparkle
    """
    amber = np.array(hex_to_rgb01("#FFBF00"), dtype=np.float32)
    gold = np.array(hex_to_rgb01("#FFD700"), dtype=np.float32)
    warm_white = np.array((1.0, 0.97, 0.92), dtype=np.float32)

    palette = np.array([amber, gold, warm_white], dtype=np.float32)
    weights = np.array([0.46, 0.40, 0.14], dtype=np.float32)
    picks = np.random.choice(3, size=count, p=weights)

    base = palette[picks]
    brightness = np.random.uniform(0.78, 1.22, (count, 1)).astype(np.float32)
    rgb = np.clip(base * brightness, 0.0, 1.0)
    alpha = np.random.uniform(0.60, 0.98, (count, 1)).astype(np.float32)

    return np.hstack((rgb, alpha)).astype(np.float32)


class ParticleOrbRenderer:
    """Stores particle data in GPU buffers (VBO) for fast rendering."""

    def __init__(self, count: int):
        self.count = int(np.clip(count, 5000, 8000))
        self.positions = build_sphere_shell_positions(self.count)
        self.colors = build_particle_colors(self.count)
        self.position_vbo = glGenBuffers(1)
        self.color_vbo = glGenBuffers(1)
        self._upload_buffers()

    def _upload_buffers(self) -> None:
        glBindBuffer(GL_ARRAY_BUFFER, self.position_vbo)
        glBufferData(GL_ARRAY_BUFFER, self.positions.nbytes, self.positions, GL_STATIC_DRAW)

        glBindBuffer(GL_ARRAY_BUFFER, self.color_vbo)
        glBufferData(GL_ARRAY_BUFFER, self.colors.nbytes, self.colors, GL_STATIC_DRAW)

        glBindBuffer(GL_ARRAY_BUFFER, 0)

    def draw(self, pulse_scale: float) -> None:
        # Dust-like tiny points.
        glEnable(GL_POINT_SMOOTH)
        glHint(GL_POINT_SMOOTH_HINT, GL_NICEST)

        # Pass 1: soft glow
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glPointSize(1.75 + pulse_scale * 0.25)
        self._draw_arrays()

        # Pass 2: subtle additive sparkle
        glBlendFunc(GL_SRC_ALPHA, GL_ONE)
        glPointSize(0.95 + pulse_scale * 0.12)
        self._draw_arrays()

        # Restore alpha blending mode.
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

    def _draw_arrays(self) -> None:
        glEnableClientState(GL_VERTEX_ARRAY)
        glEnableClientState(GL_COLOR_ARRAY)

        glBindBuffer(GL_ARRAY_BUFFER, self.position_vbo)
        glVertexPointer(3, GL_FLOAT, 0, None)

        glBindBuffer(GL_ARRAY_BUFFER, self.color_vbo)
        glColorPointer(4, GL_FLOAT, 0, None)

        glDrawArrays(GL_POINTS, 0, self.count)

        glBindBuffer(GL_ARRAY_BUFFER, 0)
        glDisableClientState(GL_COLOR_ARRAY)
        glDisableClientState(GL_VERTEX_ARRAY)


def set_3d_projection(width: int, height: int) -> None:
    aspect = max(width / max(height, 1), 1e-4)
    glViewport(0, 0, width, height)
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    gluPerspective(45.0, aspect, 0.1, 100.0)
    glMatrixMode(GL_MODELVIEW)
    glLoadIdentity()


def draw_background_gradient(width: int, height: int) -> None:
    """
    Draw deep dark-brown background with a subtle center glow.
    Base target color is #1a1510 as requested.
    """
    edge = hex_to_rgb01("#1a1510")
    center = hex_to_rgb01("#3a250f")

    glDisable(GL_DEPTH_TEST)

    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity()
    glOrtho(0, width, 0, height, -1, 1)

    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()

    # Base fullscreen fill
    glBegin(GL_QUADS)
    glColor4f(edge[0], edge[1], edge[2], 1.0)
    glVertex2f(0, 0)
    glVertex2f(width, 0)
    glVertex2f(width, height)
    glVertex2f(0, height)
    glEnd()

    # Center radial glow to mimic cinematic backdrop.
    cx = width * 0.5
    cy = height * 0.42
    radius = min(width, height) * 0.68
    segments = 80

    glBegin(GL_TRIANGLE_FAN)
    glColor4f(center[0], center[1], center[2], 0.44)
    glVertex2f(cx, cy)
    for i in range(segments + 1):
        a = (i / segments) * (2.0 * math.pi)
        glColor4f(edge[0], edge[1], edge[2], 0.0)
        glVertex2f(cx + math.cos(a) * radius, cy + math.sin(a) * radius)
    glEnd()

    glPopMatrix()
    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    glMatrixMode(GL_MODELVIEW)

    glEnable(GL_DEPTH_TEST)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Shell 3D Particle Orb")
    parser.add_argument(
        "--particles",
        type=int,
        default=6800,
        help="Particle count (5000 to 8000).",
    )
    parser.add_argument("--width", type=int, default=1280, help="Window width.")
    parser.add_argument("--height", type=int, default=800, help="Window height.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    particle_count = int(np.clip(args.particles, 5000, 8000))

    pygame.init()
    pygame.display.set_caption("Shell 3D Particle Orb")
    pygame.display.set_mode(
        (args.width, args.height),
        pygame.OPENGL | pygame.DOUBLEBUF | pygame.RESIZABLE,
    )

    glClearColor(0.0, 0.0, 0.0, 1.0)
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    glEnable(GL_DEPTH_TEST)
    glDepthFunc(GL_LEQUAL)

    width, height = args.width, args.height
    set_3d_projection(width, height)

    orb = ParticleOrbRenderer(particle_count)

    clock = pygame.time.Clock()
    t = 0.0
    yaw = 0.0

    running = True
    while running:
        dt = clock.tick(60) / 1000.0
        t += dt

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False
            elif event.type == pygame.VIDEORESIZE:
                width = max(event.w, 360)
                height = max(event.h, 420)
                pygame.display.set_mode(
                    (width, height),
                    pygame.OPENGL | pygame.DOUBLEBUF | pygame.RESIZABLE,
                )
                set_3d_projection(width, height)

        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        draw_background_gradient(width, height)

        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()

        # Keep orb centered with slight floating motion.
        float_y = math.sin(t * 0.85) * 0.12
        glTranslatef(0.0, float_y, -8.0)

        # Slow cinematic rotation on Y and X.
        yaw += dt * 9.0
        pitch = math.sin(t * 0.42) * 13.0
        glRotatef(pitch, 1.0, 0.0, 0.0)
        glRotatef(yaw, 0.0, 1.0, 0.0)

        pulse = 0.5 + 0.5 * math.sin(t * 1.25)
        orb.draw(pulse)

        pygame.display.flip()

    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()
