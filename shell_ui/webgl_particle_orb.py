"""webgl_particle_orb — Three.js particle sphere as a drop-in for VoiceVisualizer.

A Qt widget that hosts a QWebEngineView running an inline Three.js scene:

  * ~3000 particles arranged on a sphere via spherical coordinates (theta/phi)
  * BufferGeometry + PointsMaterial with additive blending → cheap glow / bloom feel
  * Per-particle size + opacity variation
  * Mouse-drag rotation with damping (deltaX → Y axis, deltaY → X axis, lerp)
  * "Speaking" trigger → outward explode (ease-out) and auto-implode back
  * Live amplitude → orb pulse intensity + color hue
  * Dark transparent background — sits over the existing voice page card

Public API matches `VoiceVisualizer` so it can swap in without touching callers:

    orb = WebGLParticleOrb(parent)
    orb.clicked.connect(...)        # tap-to-toggle session
    orb.set_amplitude(0.0..1.0)
    orb.set_state("idle"|"listening"|"speaking"|"muted"|"error")
    orb.set_speaking(True/False)
    orb._tick_timer                  # dummy QTimer (compat with old code)

Qt → JS:  via QWebEnginePage.runJavaScript("window.shellOrb.cmd(...)")
JS  → Qt: by mutating `document.title` ("orb-click:<ts>") which Qt reads via
          QWebEnginePage.titleChanged. No QWebChannel boilerplate needed.
"""
from __future__ import annotations

import json
import logging
from typing import Optional

from PyQt6.QtCore import Qt, QSize, QTimer, pyqtSignal, QUrl
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QSizePolicy

logger = logging.getLogger("shell_ui.webgl_orb")

try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView  # type: ignore
    from PyQt6.QtWebEngineCore import QWebEngineSettings  # type: ignore
    _WEB_OK = True
except Exception as _e:  # pragma: no cover
    QWebEngineView = None  # type: ignore
    QWebEngineSettings = None  # type: ignore
    _WEB_OK = False
    logger.warning("QtWebEngine unavailable — WebGLParticleOrb disabled (%s)", _e)


# ---------------------------------------------------------------------------
# HTML payload — Three.js scene in a single self-contained document.
# Three.js is loaded from a CDN; if the user is offline the orb degrades
# to a plain dark canvas with a glowing ring fallback (drawn in 2D).
# ---------------------------------------------------------------------------

_ORB_HTML = r"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>shell-orb-init</title>
<style>
  html,body{margin:0;padding:0;width:100%;height:100%;overflow:hidden;
    background:transparent;cursor:grab;}
  body.dragging{cursor:grabbing;}
  canvas{display:block;width:100%!important;height:100%!important;background:transparent;}
  #fb{position:absolute;inset:0;display:none;align-items:center;justify-content:center;
    color:#A78BFA;font:12px/1.4 'Segoe UI',sans-serif;letter-spacing:2px;text-align:center;}
</style></head>
<body>
<div id="fb">SHELL ORB · WEBGL UNAVAILABLE</div>
<script src="https://unpkg.com/three@0.158.0/build/three.min.js"
  onerror="document.getElementById('fb').style.display='flex';"></script>
<script>
(()=>{
  // Wait for Three.js — if CDN is blocked we'll bail to fallback.
  function waitFor(name, cb, tries){
    if(window[name])return cb();
    if((tries|0)>40){document.getElementById('fb').style.display='flex';return;}
    setTimeout(()=>waitFor(name,cb,(tries|0)+1),50);
  }
  waitFor('THREE', init, 0);

  function init(){
    const THREE = window.THREE;
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(50, 1, 0.1, 100);
    camera.position.z = 2.6;
    const renderer = new THREE.WebGLRenderer({antialias:true, alpha:true,
      preserveDrawingBuffer:false});
    renderer.setPixelRatio(Math.min(window.devicePixelRatio||1, 2));
    renderer.setClearColor(0x000000, 0);
    document.body.appendChild(renderer.domElement);
    scene.add(new THREE.AmbientLight(0xffffff, 0.6));

    function resize(){
      const w = window.innerWidth, h = window.innerHeight;
      renderer.setSize(w, h, false);
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
    }
    resize();
    window.addEventListener('resize', resize);

    // ---------- State palette (mirrors Shell-v2 InstancedMesh orb) ----
    const STATE_COLORS = {
      idle:      new THREE.Color(0xA78BFA),  // violet — calm presence
      listening: new THREE.Color(0x22D3EE),  // cyan   — attention
      thinking:  new THREE.Color(0xF59E0B),  // amber  — work
      speaking:  new THREE.Color(0x10B981),  // emerald — output
      muted:     new THREE.Color(0x6B7280),  // gray   — quiet
      error:     new THREE.Color(0xEF4444),  // red    — alert
    };
    const STATE_SPEED = {
      idle: 0.06, listening: 0.12, thinking: 0.28,
      speaking: 0.18, muted: 0.02, error: 0.20,
    };

    // ---------- Fibonacci sphere distribution (5000 points) -----------
    const N = 5000;
    function fibonacciSphere(n){
      const out = new Float32Array(n * 3);
      const phi = Math.PI * (Math.sqrt(5) - 1);
      for (let i = 0; i < n; i++) {
        const y = 1 - (i / Math.max(1, n - 1)) * 2;
        const r = Math.sqrt(1 - y*y);
        const theta = phi * i;
        out[i*3+0] = Math.cos(theta) * r;
        out[i*3+1] = y;
        out[i*3+2] = Math.sin(theta) * r;
      }
      return out;
    }
    const positions = fibonacciSphere(N);

    // Per-particle phase offsets so motion looks organic.
    const phases = new Float32Array(N);
    for (let i = 0; i < N; i++) phases[i] = Math.random() * Math.PI * 2;

    // ---------- InstancedMesh: one tiny low-poly sphere per particle ---
    const sphereGeo = new THREE.SphereGeometry(1, 6, 6);
    const sphereMat = new THREE.MeshBasicMaterial({
      color: STATE_COLORS.idle.clone(),
      transparent: true,
      opacity: 0.85,
    });
    const mesh = new THREE.InstancedMesh(sphereGeo, sphereMat, N);
    scene.add(mesh);

    // ---------- Halo (transparent sphere with gentle pulse) ----------
    const haloGeo = new THREE.SphereGeometry(1, 32, 32);
    const haloMat = new THREE.MeshBasicMaterial({
      color: STATE_COLORS.idle.clone(),
      transparent: true,
      opacity: 0.08,
    });
    const halo = new THREE.Mesh(haloGeo, haloMat);
    scene.add(halo);

    // ---------- State machine -----------------------------------------
    const state = {
      mode: 'idle',
      currentColor: STATE_COLORS.idle.clone(),
      targetColor: STATE_COLORS.idle.clone(),
      currentSpeed: 0.06,
      targetSpeed: 0.06,
      explode: 0, explodeTarget: 0,    // burst on speaking
      pulseTarget: 0,                  // live amplitude
      pulse: 0,
      rotX: 0, rotY: 0,
      targetRotX: 0, targetRotY: 0,
    };

    // Mouse drag rotation with damping (deltaX -> Y axis, deltaY -> X)
    let dragging = false, lastX = 0, lastY = 0;
    function pointerDown(e){
      dragging = true;
      const t = e.touches ? e.touches[0] : e;
      lastX = t.clientX; lastY = t.clientY;
      document.body.classList.add('dragging');
    }
    function pointerMove(e){
      if (!dragging) return;
      const t = e.touches ? e.touches[0] : e;
      const dx = t.clientX - lastX;
      const dy = t.clientY - lastY;
      lastX = t.clientX; lastY = t.clientY;
      state.targetRotY += dx * 0.0065;
      state.targetRotX += dy * 0.0065;
      state.targetRotX = Math.max(-1.4, Math.min(1.4, state.targetRotX));
    }
    function pointerUp(){
      dragging = false;
      document.body.classList.remove('dragging');
    }
    // Tap-to-toggle: only register if the pointer barely moved.
    let tapDownX = 0, tapDownY = 0, tapDownT = 0;
    renderer.domElement.addEventListener('pointerdown', e=>{
      tapDownX = e.clientX; tapDownY = e.clientY; tapDownT = performance.now();
      pointerDown(e);
    });
    window.addEventListener('pointermove', pointerMove);
    window.addEventListener('pointerup', e=>{
      const dx = e.clientX - tapDownX, dy = e.clientY - tapDownY;
      const dt = performance.now() - tapDownT;
      pointerUp();
      if (dx*dx + dy*dy < 25 && dt < 400) {
        // Channel JS -> Qt: title change carries timestamp so dup-frames differ.
        document.title = 'orb-click:' + Date.now();
      }
    });
    renderer.domElement.addEventListener('touchstart', pointerDown, {passive:true});
    renderer.domElement.addEventListener('touchmove',  pointerMove, {passive:true});
    renderer.domElement.addEventListener('touchend',   pointerUp,   {passive:true});

    // Public bridge — Qt calls these via runJavaScript()
    window.shellOrb = {
      setAmplitude(a){ state.pulseTarget = Math.max(0, Math.min(1, a)); },
      setState(s){
        state.mode = s;
        if (STATE_COLORS[s]) state.targetColor.copy(STATE_COLORS[s]);
        if (STATE_SPEED[s] != null) state.targetSpeed = STATE_SPEED[s];
        if (s === 'speaking') {
          state.explodeTarget = 0.55;
          setTimeout(()=>{ state.explodeTarget = 0.18; }, 320);
        } else if (s === 'thinking') {
          state.explodeTarget = 0.18;
        } else if (s === 'error') {
          state.explodeTarget = 0.30;
          setTimeout(()=>{ state.explodeTarget = 0.0; }, 600);
        } else {
          state.explodeTarget = 0.0;
        }
      },
      // Manually trigger an explode burst (useful when reply lands).
      burst(){ state.explodeTarget = 0.7; setTimeout(()=>{ state.explodeTarget = 0.0; }, 700); },
    };

    // ---------- Animation loop ----------------------------------------
    const dummy = new THREE.Object3D();
    let lastT = performance.now();
    function animate(){
      const now = performance.now();
      const delta = (now - lastT) * 0.001;
      lastT = now;
      const t = now * 0.001;

      // Damped lerps.
      state.currentColor.lerp(state.targetColor, Math.min(1, delta * 3));
      state.currentSpeed += (state.targetSpeed - state.currentSpeed) * 0.06;
      state.explode += (state.explodeTarget - state.explode) * 0.10;
      state.pulse   += (state.pulseTarget   - state.pulse)   * 0.15;
      state.pulseTarget *= 0.92;
      state.rotX += (state.targetRotX - state.rotX) * 0.08;
      state.rotY += (state.targetRotY - state.rotY) * 0.08;
      if (!dragging) state.targetRotY += state.currentSpeed * 0.4 * delta * 60;

      const speed = state.currentSpeed;
      const baseRadius = 1.0;
      const breath = 1 + Math.sin(t * speed * 4) * 0.04;
      const amp = state.pulse * 0.18;

      // Update each instance: positioned on Fibonacci sphere with
      // breathing + per-particle wobble + radial pulse.
      for (let i = 0; i < N; i++) {
        const ix = i * 3;
        const px = positions[ix+0];
        const py = positions[ix+1];
        const pz = positions[ix+2];
        const phase = phases[i];
        const wobble = 1 + Math.sin(t * speed * 6 + phase) * 0.02;
        const r = baseRadius * breath * wobble * (1 + amp * (0.6 + 0.4 * (phase / (Math.PI*2))));
        const rOut = r + state.explode * (0.7 + (phase % 1) * 0.6) * 0.6;
        dummy.position.set(px * rOut, py * rOut, pz * rOut);
        const sc = 0.012 + Math.sin(t * speed * 8 + phase) * 0.004;
        dummy.scale.setScalar(Math.max(0.004, sc));
        dummy.updateMatrix();
        mesh.setMatrixAt(i, dummy.matrix);
      }
      mesh.instanceMatrix.needsUpdate = true;
      mesh.rotation.x = Math.sin(t * 0.1) * 0.08 + state.rotX;
      mesh.rotation.y = state.rotY;

      // Tint mesh material + halo to current state color.
      sphereMat.color.copy(state.currentColor);
      haloMat.color.copy(state.currentColor);
      const haloPulse = 1 + Math.sin(t * speed * 4) * 0.05;
      halo.scale.setScalar(1.25 * haloPulse + state.pulse * 0.25 + state.explode * 0.35);
      haloMat.opacity = 0.06 + Math.abs(Math.sin(t * speed * 4)) * 0.06
                        + state.pulse * 0.10 + state.explode * 0.06;

      renderer.render(scene, camera);
      requestAnimationFrame(animate);
    }
    animate();

    // Mark ready so Qt can stop logging warnings.
    document.title = 'shell-orb-ready';
  }
})();
</script>
</body></html>
"""


# ---------------------------------------------------------------------------
# Widget
# ---------------------------------------------------------------------------

class WebGLParticleOrb(QWidget):
    """Drop-in replacement for VoiceVisualizer using Three.js inside a
    QWebEngineView. Same signal + method surface, no other call-sites
    need to change.
    """

    clicked = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        # Tighter footprint — at 320 max the orb sits cleanly inside the
        # voice page stage without overlapping the transcript card below.
        self.setMinimumSize(280, 280)
        self.setMaximumSize(320, 320)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setStyleSheet("background:transparent; border:none;")

        self._state = "idle"
        self._ready = False
        self._pending_amp: Optional[float] = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        if not _WEB_OK:
            # Fallback path — let caller decide what to do. We render
            # nothing here; the host will pick the legacy VoiceVisualizer.
            self._view = None
            return

        self._view = QWebEngineView(self)
        self._view.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._view.setStyleSheet("background:transparent;")
        try:
            page = self._view.page()
            page.setBackgroundColor(Qt.GlobalColor.transparent)
            s = page.settings()
            s.setAttribute(QWebEngineSettings.WebAttribute.WebGLEnabled, True)
            s.setAttribute(QWebEngineSettings.WebAttribute.Accelerated2dCanvasEnabled, True)
            s.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
            page.titleChanged.connect(self._on_title)
        except Exception as e:
            logger.debug("orb page setup partial: %s", e)
        self._view.setHtml(_ORB_HTML, QUrl("https://shellorb.local/"))
        lay.addWidget(self._view)

        # Compat — old code reads `_tick_timer`. We give it an inert one
        # so calls like `viz._tick_timer.stop()` don't blow up.
        self._tick_timer = QTimer(self)
        self._tick_timer.setInterval(1000)
        # No timeout connection — JS owns the render loop.

    # ---- Qt -> JS bridge -----------------------------------------------
    def _js(self, code: str) -> None:
        if not self._view or not self._ready:
            return
        try:
            self._view.page().runJavaScript(code)
        except Exception as e:
            logger.debug("orb JS call failed: %s", e)

    # ---- JS -> Qt bridge (titleChanged carries clicks + ready signal) --
    def _on_title(self, title: str) -> None:
        if not title:
            return
        if title == "shell-orb-ready":
            self._ready = True
            # Replay deferred amplitude / state.
            self._js(f"window.shellOrb && window.shellOrb.setState({json.dumps(self._state)});")
            if self._pending_amp is not None:
                self._js(f"window.shellOrb && window.shellOrb.setAmplitude({self._pending_amp});")
                self._pending_amp = None
            return
        if title.startswith("orb-click:"):
            try:
                self.clicked.emit()
            except Exception:
                pass

    # ---- Public API (mirrors VoiceVisualizer) --------------------------

    def set_amplitude(self, amp) -> None:
        try:
            a = max(0.0, min(1.0, float(amp)))
        except Exception:
            a = 0.0
        if not self._ready:
            self._pending_amp = a
            return
        self._js(f"window.shellOrb && window.shellOrb.setAmplitude({a});")

    def set_state(self, state: str) -> None:
        if state == self._state:
            return
        self._state = state
        self._js(f"window.shellOrb && window.shellOrb.setState({json.dumps(state)});")

    def set_speaking(self, speaking: bool) -> None:
        if speaking:
            self.set_state("speaking")
        elif self._state == "speaking":
            self.set_state("listening")

    def burst(self) -> None:
        """Trigger a one-shot outward explode. Useful when reply lands."""
        self._js("window.shellOrb && window.shellOrb.burst && window.shellOrb.burst();")

    # Reasonable size hints so the layout treats us like the old viz.
    def sizeHint(self) -> QSize:
        return QSize(300, 300)

    def minimumSizeHint(self) -> QSize:
        return QSize(280, 280)


__all__ = ["WebGLParticleOrb"]
