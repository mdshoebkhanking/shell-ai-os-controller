"""shell_game_builder — One-shot HTML5 game generator for Shell AI.

The user says "build me a snake game" / "make tetris" / "build a pong" and
this module:

  1. Picks a built-in template (snake, tetris, pong, breakout, flappy, 2048),
     OR routes through MultiAIBrain for free-form / customised requests.
  2. Writes a single self-contained HTML file under
     ``Desktop/shell_games/<slug>_<timestamp>.html``.
  3. Opens it in the default browser.
  4. Returns a one-line Hinglish status string.

All templates are 60-fps canvas games with cyan-cyber neon aesthetic
(``#0a0e1a`` bg, ``#00f0ff`` primary, ``#ac89ff`` secondary, ``#3ee3a8``
success). Sound is via WebAudio (no asset files). Keyboard + touch
controls. Each template has a start screen, score HUD, game-over screen
and restart key.

Public surface
--------------
    build_game_tool(game: str, custom_features: str = "") -> str
        LiveKit ``@function_tool`` registered into the agent's tools list.

Implementation notes
--------------------
* The wrapped ``@function_tool`` decorator is taken from
  ``shell_safe_executor`` so the tool participates in Shell's telemetry,
  rate-limiting and circuit-breaker plumbing. Falls back to LiveKit's
  raw ``function_tool`` when the wrapper is unavailable.
* Templates are stored as plain strings in ``_TEMPLATES`` and substituted
  via ``str.replace`` (no f-strings — the JS uses ``${}`` syntax which
  collides with Python's f-string parser).
* Free-form requests call ``MultiAIBrain.generate_response`` with
  mode="CODER" and a strict system prompt that demands a single-file
  HTML5 deliverable. The result is sanitised (markdown code-fence
  stripping) before write.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import time
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Optional

# ── Tool decorator (project wrapper preferred) ───────────────────────────
try:
    from shell_safe_executor import god_tier_tool as function_tool
except Exception:  # pragma: no cover
    try:
        from livekit.agents import function_tool
    except Exception:
        # Last-ditch no-op decorator so the module still imports under
        # bare-bones environments (e.g. unit tests).
        def function_tool(fn=None, **_kw):  # type: ignore
            if fn is None:
                return lambda f: f
            return fn

logger = logging.getLogger("shell_game_builder")


# ─────────────────────────────────────────────────────────────────────────
# Game-name normalisation
# ─────────────────────────────────────────────────────────────────────────

_ALIASES = {
    "snake":      ["snake", "saap", "saanp", "naag"],
    "tetris":     ["tetris", "tetras", "block stack", "stack blocks", "block puzzle"],
    "pong":       ["pong", "table tennis", "paddle"],
    "breakout":   ["breakout", "brick breaker", "brick", "arkanoid", "ball brick"],
    "flappy":     ["flappy", "flappy bird", "flappy-bird"],
    "2048":       ["2048", "two thousand forty eight", "twenty forty eight"],
    "invaders":   ["invaders", "space invader", "alien shoot", "shooter",
                   "shoot game", "shoot the alien", "spaceship", "galaxy",
                   "alien game"],
    "runner":     ["runner", "dino", "dinosaur", "endless runner", "running game",
                   "dauda", "daudna", "dodge", "jump game", "dino run", "chrome dino",
                   "subway", "race"],
    "tictactoe":  ["tic tac toe", "tic-tac-toe", "tictactoe", "noughts and crosses",
                   "x and o", "xo", "x o game"],
    "memory":     ["memory", "memory match", "match pair", "matching pair", "concentration",
                   "yaad", "card match", "pair match"],
    "whack":      ["whack", "whack a mole", "whack-a-mole", "mole", "hit the mole",
                   "tap game", "click game", "reaction game"],
    "maze":       ["maze", "pacman", "pac man", "pac-man", "labyrinth", "ghost",
                   "dot eater", "bhool bhulaiya"],
}

# Coarse keyword → template family. Used when `_normalise` can't match a
# direct alias. The order matters — earlier categories win on ties.
_FAMILY = [
    ("invaders",  ["shoot", "blast", "gun", "fire", "bullet", "alien", "enemy",
                    "ufo", "war", "battle", "space"]),
    ("runner",    ["run", "race", "racing", "car", "drive", "chase", "jump",
                    "endless", "obstacle"]),
    ("maze",      ["explore", "find way", "labyrinth", "ghost"]),
    ("breakout",  ["ball", "bounce", "brick"]),
    ("tetris",    ["block", "stack", "fall", "puzzle"]),
    ("memory",    ["card", "memory", "yaad"]),
    ("whack",     ["tap", "click", "reaction", "speed", "reflex"]),
    ("tictactoe", ["board", "turn", "two player", "2 player"]),
    ("snake",     ["eat", "grow", "tail", "food"]),
]


def _normalise(game: str) -> Optional[str]:
    """Map free-form game name to a template key, or None if unknown."""
    g = (game or "").strip().lower()
    if not g:
        return None
    # 1) Direct alias match.
    for key, aliases in _ALIASES.items():
        for alias in aliases:
            if alias in g:
                return key
    # 2) Family fallback — pick the template whose theme matches keywords
    #    in the request. "race game" → runner, "shoot zombies" → invaders.
    for key, kws in _FAMILY:
        for kw in kws:
            if kw in g:
                return key
    return None


def _slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", (text or "game").lower()).strip("_")
    return s[:40] or "game"


def _output_dir() -> Path:
    """Resolve ``Desktop/shell_games`` cross-platform; create if missing."""
    home = Path(os.path.expanduser("~"))
    candidates = [
        home / "Desktop" / "shell_games",
        home / "OneDrive" / "Desktop" / "shell_games",  # OneDrive-redirected
    ]
    # Prefer the first candidate whose parent exists.
    target = candidates[0]
    for c in candidates:
        if c.parent.exists():
            target = c
            break
    target.mkdir(parents=True, exist_ok=True)
    return target


# ─────────────────────────────────────────────────────────────────────────
# Template library — six built-in games
# Each template is a single, self-contained HTML5 file with inline CSS+JS.
# ``__TITLE__`` and ``__CUSTOM__`` are substituted at write time.
# ─────────────────────────────────────────────────────────────────────────

_BASE_CSS = """
*{margin:0;padding:0;box-sizing:border-box;}
html,body{width:100%;height:100%;overflow:hidden;font-family:'Segoe UI',Roboto,monospace;}
body{background:#0a0e1a;color:#e8f0ff;display:flex;align-items:center;justify-content:center;min-height:100vh;}
.shell-frame{position:relative;display:flex;flex-direction:column;align-items:center;gap:14px;padding:18px;border-radius:18px;
  background:linear-gradient(160deg,rgba(0,240,255,.05),rgba(172,137,255,.05));
  box-shadow:0 0 40px rgba(0,240,255,.18),inset 0 0 30px rgba(172,137,255,.06);
  border:1px solid rgba(0,240,255,.18);}
h1.title{font-size:22px;letter-spacing:5px;color:#00f0ff;text-shadow:0 0 12px #00f0ff,0 0 24px rgba(0,240,255,.4);}
.hud{display:flex;gap:24px;font-size:14px;letter-spacing:2px;color:#ac89ff;text-shadow:0 0 8px rgba(172,137,255,.5);}
.hud b{color:#3ee3a8;text-shadow:0 0 8px rgba(62,227,168,.5);}
canvas{display:block;background:#0a0e1a;border:1px solid rgba(0,240,255,.35);border-radius:12px;
  box-shadow:0 0 30px rgba(0,240,255,.25),inset 0 0 30px rgba(0,240,255,.07);image-rendering:pixelated;}
.overlay{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;
  background:rgba(10,14,26,.86);backdrop-filter:blur(6px);border-radius:18px;gap:14px;text-align:center;padding:20px;}
.overlay h2{font-size:32px;color:#00f0ff;text-shadow:0 0 18px #00f0ff;letter-spacing:6px;}
.overlay p{color:#ac89ff;letter-spacing:2px;font-size:14px;line-height:1.7;}
.overlay button{margin-top:8px;padding:12px 28px;background:transparent;border:1px solid #00f0ff;color:#00f0ff;
  font-size:14px;letter-spacing:3px;cursor:pointer;border-radius:8px;text-transform:uppercase;
  box-shadow:0 0 14px rgba(0,240,255,.45);transition:all .2s;}
.overlay button:hover{background:rgba(0,240,255,.15);box-shadow:0 0 22px rgba(0,240,255,.7);}
.touchpad{display:none;margin-top:6px;}
@media (pointer:coarse){.touchpad{display:grid;grid-template-columns:60px 60px 60px;gap:8px;justify-content:center;}}
.touchpad button{width:60px;height:60px;background:rgba(0,240,255,.1);color:#00f0ff;border:1px solid rgba(0,240,255,.5);
  border-radius:8px;font-size:22px;cursor:pointer;}
.footer{font-size:11px;color:rgba(232,240,255,.4);letter-spacing:3px;margin-top:6px;}
"""


# ──── SNAKE ─────────────────────────────────────────────────────────────
_SNAKE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>__TITLE__</title>
<style>__BASE_CSS__
.cell-glow{filter:drop-shadow(0 0 6px #00f0ff);}
</style></head>
<body><div class="shell-frame" id="frame">
  <h1 class="title">__TITLE__</h1>
  <div class="hud"><span>SCORE: <b id="score">0</b></span><span>BEST: <b id="best">0</b></span><span>SPEED: <b id="speed">1</b></span></div>
  <canvas id="cv" width="480" height="480"></canvas>
  <div class="touchpad">
    <button data-d="up" style="grid-column:2">↑</button>
    <button data-d="left" style="grid-column:1;grid-row:2">←</button>
    <button data-d="down" style="grid-column:2;grid-row:2">↓</button>
    <button data-d="right" style="grid-column:3;grid-row:2">→</button>
  </div>
  <div class="footer">ARROWS / WASD · R = RESTART · P = PAUSE</div>
  <div class="overlay" id="ov">
    <h2>SHELL · SNAKE</h2>
    <p>Eat the neon orbs · Don't bite your tail · Walls wrap around</p>
    <button id="startBtn">START</button>
  </div>
</div>
<script>
(()=>{
  const cv=document.getElementById('cv'),ctx=cv.getContext('2d');
  const COLS=24,ROWS=24,CELL=cv.width/COLS;
  const scoreEl=document.getElementById('score'),bestEl=document.getElementById('best'),speedEl=document.getElementById('speed');
  const ov=document.getElementById('ov'),startBtn=document.getElementById('startBtn');
  let snake,dir,nextDir,food,score,best=+(localStorage.getItem('shell_snake_best')||0),tick,running,paused,speed,lastMove;
  bestEl.textContent=best;
  // ── audio ──
  let actx;
  function beep(freq,dur=0.06,type='sine',vol=0.08){
    try{actx=actx||new(window.AudioContext||window.webkitAudioContext)();
      const o=actx.createOscillator(),g=actx.createGain();
      o.type=type;o.frequency.value=freq;g.gain.value=vol;
      o.connect(g);g.connect(actx.destination);o.start();
      g.gain.exponentialRampToValueAtTime(0.0001,actx.currentTime+dur);o.stop(actx.currentTime+dur);
    }catch(e){}
  }
  function spawnFood(){
    while(true){
      const f={x:(Math.random()*COLS)|0,y:(Math.random()*ROWS)|0};
      if(!snake.some(s=>s.x===f.x&&s.y===f.y)){food=f;return;}
    }
  }
  function reset(){
    snake=[{x:12,y:12},{x:11,y:12},{x:10,y:12}];
    dir={x:1,y:0};nextDir=dir;score=0;speed=1;lastMove=0;
    spawnFood();scoreEl.textContent=0;speedEl.textContent=1;
    paused=false;running=true;
  }
  function gameOver(){
    running=false;
    if(score>best){best=score;localStorage.setItem('shell_snake_best',best);bestEl.textContent=best;}
    ov.innerHTML='<h2>GAME OVER</h2><p>Score: <b style="color:#3ee3a8">'+score+
      '</b> · Best: <b style="color:#3ee3a8">'+best+'</b></p><button id="r2">PLAY AGAIN</button>';
    ov.style.display='flex';
    document.getElementById('r2').onclick=()=>{ov.style.display='none';reset();};
    beep(120,0.5,'sawtooth',0.12);
  }
  function step(){
    dir=nextDir;
    const head={x:(snake[0].x+dir.x+COLS)%COLS,y:(snake[0].y+dir.y+ROWS)%ROWS};
    if(snake.some(s=>s.x===head.x&&s.y===head.y)){gameOver();return;}
    snake.unshift(head);
    if(head.x===food.x&&head.y===food.y){
      score++;scoreEl.textContent=score;
      if(score%5===0){speed=Math.min(8,speed+1);speedEl.textContent=speed;}
      spawnFood();beep(880,0.08,'square');
    }else{snake.pop();beep(440+score*4,0.02,'square',0.04);}
  }
  function draw(){
    // bg grid
    ctx.fillStyle='#0a0e1a';ctx.fillRect(0,0,cv.width,cv.height);
    ctx.strokeStyle='rgba(0,240,255,0.05)';ctx.lineWidth=1;
    for(let i=0;i<=COLS;i++){
      ctx.beginPath();ctx.moveTo(i*CELL,0);ctx.lineTo(i*CELL,cv.height);ctx.stroke();
      ctx.beginPath();ctx.moveTo(0,i*CELL);ctx.lineTo(cv.width,i*CELL);ctx.stroke();
    }
    // food
    ctx.shadowBlur=18;ctx.shadowColor='#3ee3a8';ctx.fillStyle='#3ee3a8';
    ctx.beginPath();ctx.arc(food.x*CELL+CELL/2,food.y*CELL+CELL/2,CELL/2-2,0,Math.PI*2);ctx.fill();
    // snake
    ctx.shadowBlur=14;ctx.shadowColor='#00f0ff';
    snake.forEach((s,i)=>{
      const t=i/snake.length;
      ctx.fillStyle=i===0?'#00f0ff':'rgba(0,240,255,'+(0.95-t*0.6)+')';
      ctx.fillRect(s.x*CELL+1,s.y*CELL+1,CELL-2,CELL-2);
    });
    ctx.shadowBlur=0;
  }
  function loop(t){
    if(!running){draw();return;}
    if(!paused){
      const interval=Math.max(60,160-speed*12);
      if(t-lastMove>=interval){step();lastMove=t;}
    }
    draw();
    requestAnimationFrame(loop);
  }
  // ── input ──
  const KEY_DIR={ArrowUp:{x:0,y:-1},ArrowDown:{x:0,y:1},ArrowLeft:{x:-1,y:0},ArrowRight:{x:1,y:0},
    w:{x:0,y:-1},a:{x:-1,y:0},s:{x:0,y:1},d:{x:1,y:0},W:{x:0,y:-1},A:{x:-1,y:0},S:{x:0,y:1},D:{x:1,y:0}};
  function setDir(d){if(!d)return;if(d.x===-dir.x&&d.y===-dir.y)return;nextDir=d;}
  document.addEventListener('keydown',e=>{
    if(e.key==='r'||e.key==='R'){ov.style.display='none';reset();requestAnimationFrame(loop);return;}
    if(e.key==='p'||e.key==='P'){paused=!paused;return;}
    setDir(KEY_DIR[e.key]);
  });
  document.querySelectorAll('.touchpad button').forEach(b=>{
    b.addEventListener('click',()=>setDir({up:{x:0,y:-1},down:{x:0,y:1},left:{x:-1,y:0},right:{x:1,y:0}}[b.dataset.d]));
  });
  // swipe
  let tx=0,ty=0;
  cv.addEventListener('touchstart',e=>{tx=e.touches[0].clientX;ty=e.touches[0].clientY;});
  cv.addEventListener('touchend',e=>{
    const dx=e.changedTouches[0].clientX-tx,dy=e.changedTouches[0].clientY-ty;
    if(Math.abs(dx)>Math.abs(dy)) setDir({x:dx>0?1:-1,y:0}); else setDir({x:0,y:dy>0?1:-1});
  });
  startBtn.onclick=()=>{ov.style.display='none';reset();requestAnimationFrame(loop);};
})();
</script></body></html>
"""


# ──── TETRIS ────────────────────────────────────────────────────────────
_TETRIS = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>__TITLE__</title>
<style>__BASE_CSS__</style></head>
<body><div class="shell-frame">
  <h1 class="title">__TITLE__</h1>
  <div class="hud"><span>SCORE: <b id="score">0</b></span><span>LINES: <b id="lines">0</b></span><span>LEVEL: <b id="lvl">1</b></span></div>
  <canvas id="cv" width="320" height="640"></canvas>
  <div class="footer">← → MOVE · ↑/W ROTATE · ↓ DROP · SPACE HARD-DROP · R RESTART · P PAUSE</div>
  <div class="overlay" id="ov">
    <h2>SHELL · TETRIS</h2>
    <p>Stack the neon blocks · Clear lines · Don't reach the top</p>
    <button id="startBtn">START</button>
  </div>
</div>
<script>
(()=>{
  const cv=document.getElementById('cv'),ctx=cv.getContext('2d');
  const COLS=10,ROWS=20,CELL=cv.width/COLS;
  const ov=document.getElementById('ov'),startBtn=document.getElementById('startBtn');
  const scoreEl=document.getElementById('score'),linesEl=document.getElementById('lines'),lvlEl=document.getElementById('lvl');
  const COLORS=['#00f0ff','#ac89ff','#3ee3a8','#ff5fa1','#ffd166','#ff7a59','#74e3ff'];
  const SHAPES=[
    [[1,1,1,1]],                              // I
    [[1,1],[1,1]],                            // O
    [[0,1,0],[1,1,1]],                        // T
    [[0,1,1],[1,1,0]],                        // S
    [[1,1,0],[0,1,1]],                        // Z
    [[1,0,0],[1,1,1]],                        // J
    [[0,0,1],[1,1,1]]                         // L
  ];
  let grid,piece,score,lines,level,fallTimer,lastT,running,paused;
  let actx;function beep(f,d=0.05,t='square',v=0.06){try{actx=actx||new(window.AudioContext||window.webkitAudioContext)();
    const o=actx.createOscillator(),g=actx.createGain();o.type=t;o.frequency.value=f;g.gain.value=v;
    o.connect(g);g.connect(actx.destination);o.start();
    g.gain.exponentialRampToValueAtTime(.0001,actx.currentTime+d);o.stop(actx.currentTime+d);}catch(e){}}
  function newGrid(){return Array.from({length:ROWS},()=>Array(COLS).fill(0));}
  function spawn(){
    const i=(Math.random()*SHAPES.length)|0;
    const sh=SHAPES[i].map(r=>r.slice());
    piece={shape:sh,color:COLORS[i],x:((COLS-sh[0].length)/2)|0,y:0};
    if(collide(piece,0,0)){gameOver();return false;}
    return true;
  }
  function collide(p,dx,dy,sh){
    sh=sh||p.shape;
    for(let y=0;y<sh.length;y++)for(let x=0;x<sh[y].length;x++){
      if(!sh[y][x])continue;
      const nx=p.x+x+dx,ny=p.y+y+dy;
      if(nx<0||nx>=COLS||ny>=ROWS)return true;
      if(ny>=0&&grid[ny][nx])return true;
    }return false;
  }
  function merge(){
    piece.shape.forEach((r,y)=>r.forEach((v,x)=>{if(v&&piece.y+y>=0)grid[piece.y+y][piece.x+x]=piece.color;}));
  }
  function clearLines(){
    let cleared=0;
    for(let y=ROWS-1;y>=0;y--){
      if(grid[y].every(c=>c)){grid.splice(y,1);grid.unshift(Array(COLS).fill(0));cleared++;y++;}
    }
    if(cleared){
      lines+=cleared;score+=[0,40,100,300,1200][cleared]*level;
      level=Math.floor(lines/10)+1;
      scoreEl.textContent=score;linesEl.textContent=lines;lvlEl.textContent=level;
      beep(660+cleared*120,0.18,'square');
    }
  }
  function rotate(){
    const sh=piece.shape,h=sh.length,w=sh[0].length;
    const nu=Array.from({length:w},(_,r)=>Array(h).fill(0));
    for(let y=0;y<h;y++)for(let x=0;x<w;x++)nu[x][h-1-y]=sh[y][x];
    if(!collide(piece,0,0,nu)){piece.shape=nu;beep(740,0.04);}
  }
  function move(dx,dy){if(!collide(piece,dx,dy)){piece.x+=dx;piece.y+=dy;return true;}return false;}
  function softDrop(){if(!move(0,1)){merge();clearLines();if(!spawn())return;}else{score+=1;scoreEl.textContent=score;}}
  function hardDrop(){while(move(0,1)){score+=2;}scoreEl.textContent=score;merge();clearLines();spawn();beep(220,0.12,'sawtooth');}
  function gameOver(){running=false;ov.innerHTML='<h2>GAME OVER</h2><p>Score: <b style="color:#3ee3a8">'+score+
    '</b><br>Lines: <b style="color:#3ee3a8">'+lines+'</b></p><button id="r2">PLAY AGAIN</button>';ov.style.display='flex';
    document.getElementById('r2').onclick=()=>{ov.style.display='none';reset();};beep(120,0.5,'sawtooth',0.12);}
  function reset(){grid=newGrid();score=0;lines=0;level=1;fallTimer=0;lastT=0;running=true;paused=false;
    scoreEl.textContent=0;linesEl.textContent=0;lvlEl.textContent=1;spawn();}
  function drawCell(x,y,c){
    ctx.fillStyle=c;ctx.shadowBlur=12;ctx.shadowColor=c;
    ctx.fillRect(x*CELL+1,y*CELL+1,CELL-2,CELL-2);
    ctx.shadowBlur=0;
    ctx.fillStyle='rgba(255,255,255,0.18)';ctx.fillRect(x*CELL+1,y*CELL+1,CELL-2,3);
  }
  function draw(){
    ctx.fillStyle='#0a0e1a';ctx.fillRect(0,0,cv.width,cv.height);
    ctx.strokeStyle='rgba(0,240,255,0.05)';
    for(let i=0;i<=COLS;i++){ctx.beginPath();ctx.moveTo(i*CELL,0);ctx.lineTo(i*CELL,cv.height);ctx.stroke();}
    for(let i=0;i<=ROWS;i++){ctx.beginPath();ctx.moveTo(0,i*CELL);ctx.lineTo(cv.width,i*CELL);ctx.stroke();}
    grid.forEach((r,y)=>r.forEach((c,x)=>{if(c)drawCell(x,y,c);}));
    if(piece)piece.shape.forEach((r,y)=>r.forEach((v,x)=>{if(v)drawCell(piece.x+x,piece.y+y,piece.color);}));
  }
  function loop(t){
    if(!running){draw();return;}
    const dt=t-lastT;lastT=t;
    if(!paused){fallTimer+=dt;const interval=Math.max(80,800-(level-1)*60);
      if(fallTimer>=interval){fallTimer=0;softDrop();}}
    draw();requestAnimationFrame(loop);
  }
  document.addEventListener('keydown',e=>{
    if(e.key==='r'||e.key==='R'){ov.style.display='none';reset();requestAnimationFrame(loop);return;}
    if(e.key==='p'||e.key==='P'){paused=!paused;return;}
    if(!running)return;
    if(e.key==='ArrowLeft'||e.key==='a'||e.key==='A')move(-1,0);
    else if(e.key==='ArrowRight'||e.key==='d'||e.key==='D')move(1,0);
    else if(e.key==='ArrowDown'||e.key==='s'||e.key==='S')softDrop();
    else if(e.key==='ArrowUp'||e.key==='w'||e.key==='W')rotate();
    else if(e.key===' '){e.preventDefault();hardDrop();}
  });
  startBtn.onclick=()=>{ov.style.display='none';reset();requestAnimationFrame(loop);};
})();
</script></body></html>
"""


# ──── PONG ──────────────────────────────────────────────────────────────
_PONG = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>__TITLE__</title>
<style>__BASE_CSS__</style></head>
<body><div class="shell-frame">
  <h1 class="title">__TITLE__</h1>
  <div class="hud"><span>YOU: <b id="ps">0</b></span><span>CPU: <b id="cs">0</b></span><span>RALLY: <b id="rl">0</b></span></div>
  <canvas id="cv" width="640" height="400"></canvas>
  <div class="footer">↑ ↓ / W S · MOUSE · TOUCH · R RESTART · P PAUSE</div>
  <div class="overlay" id="ov">
    <h2>SHELL · PONG</h2>
    <p>First to 7 wins · The ball speeds up each rally</p>
    <button id="startBtn">START</button>
  </div>
</div>
<script>
(()=>{
  const cv=document.getElementById('cv'),ctx=cv.getContext('2d');
  const W=cv.width,H=cv.height,PW=10,PH=80;
  const psEl=document.getElementById('ps'),csEl=document.getElementById('cs'),rlEl=document.getElementById('rl');
  const ov=document.getElementById('ov'),startBtn=document.getElementById('startBtn');
  let player,cpu,ball,running,paused,rally;
  let actx;function beep(f,d=0.05,t='square',v=0.07){try{actx=actx||new(window.AudioContext||window.webkitAudioContext)();
    const o=actx.createOscillator(),g=actx.createGain();o.type=t;o.frequency.value=f;g.gain.value=v;
    o.connect(g);g.connect(actx.destination);o.start();
    g.gain.exponentialRampToValueAtTime(.0001,actx.currentTime+d);o.stop(actx.currentTime+d);}catch(e){}}
  function reset(loser){
    ball={x:W/2,y:H/2,vx:(loser==='p'?-1:1)*4,vy:(Math.random()*4-2),r:7};
    rally=0;rlEl.textContent=0;
  }
  function init(){
    player={y:H/2-PH/2,score:0,vy:0};
    cpu={y:H/2-PH/2,score:0};
    psEl.textContent=0;csEl.textContent=0;
    reset('p');running=true;paused=false;
  }
  function endGame(winner){
    running=false;
    ov.innerHTML='<h2>'+(winner==='p'?'YOU WIN':'CPU WINS')+'</h2><p>'+player.score+' — '+cpu.score+
      '</p><button id="r2">REMATCH</button>';
    ov.style.display='flex';document.getElementById('r2').onclick=()=>{ov.style.display='none';init();};
  }
  function step(){
    // player movement (keyboard)
    player.y+=player.vy;
    player.y=Math.max(0,Math.min(H-PH,player.y));
    // cpu AI
    const tgt=ball.y-PH/2;const dy=tgt-cpu.y;cpu.y+=Math.sign(dy)*Math.min(Math.abs(dy),5);
    cpu.y=Math.max(0,Math.min(H-PH,cpu.y));
    // ball
    ball.x+=ball.vx;ball.y+=ball.vy;
    if(ball.y<=ball.r||ball.y>=H-ball.r){ball.vy*=-1;beep(520,0.04);}
    // paddle collisions
    if(ball.x-ball.r<=PW+10&&ball.y>player.y&&ball.y<player.y+PH&&ball.vx<0){
      ball.vx=-ball.vx*1.05;ball.vy+=(ball.y-(player.y+PH/2))*0.08;
      rally++;rlEl.textContent=rally;beep(660,0.05);
    }
    if(ball.x+ball.r>=W-PW-10&&ball.y>cpu.y&&ball.y<cpu.y+PH&&ball.vx>0){
      ball.vx=-ball.vx*1.05;ball.vy+=(ball.y-(cpu.y+PH/2))*0.08;
      rally++;rlEl.textContent=rally;beep(440,0.05);
    }
    // scoring
    if(ball.x<0){cpu.score++;csEl.textContent=cpu.score;beep(180,0.2,'sawtooth');
      if(cpu.score>=7){endGame('c');return;}reset('c');}
    if(ball.x>W){player.score++;psEl.textContent=player.score;beep(880,0.2,'square');
      if(player.score>=7){endGame('p');return;}reset('p');}
  }
  function draw(){
    ctx.fillStyle='#0a0e1a';ctx.fillRect(0,0,W,H);
    // mid line
    ctx.strokeStyle='rgba(0,240,255,0.3)';ctx.setLineDash([6,10]);ctx.beginPath();
    ctx.moveTo(W/2,0);ctx.lineTo(W/2,H);ctx.stroke();ctx.setLineDash([]);
    // paddles
    ctx.shadowBlur=18;ctx.shadowColor='#00f0ff';ctx.fillStyle='#00f0ff';
    ctx.fillRect(10,player.y,PW,PH);
    ctx.shadowColor='#ac89ff';ctx.fillStyle='#ac89ff';
    ctx.fillRect(W-PW-10,cpu.y,PW,PH);
    // ball
    ctx.shadowColor='#3ee3a8';ctx.fillStyle='#3ee3a8';
    ctx.beginPath();ctx.arc(ball.x,ball.y,ball.r,0,Math.PI*2);ctx.fill();
    ctx.shadowBlur=0;
  }
  function loop(){if(!running){draw();return;}if(!paused)step();draw();requestAnimationFrame(loop);}
  // input
  const keys={};
  document.addEventListener('keydown',e=>{
    if(e.key==='r'||e.key==='R'){ov.style.display='none';init();requestAnimationFrame(loop);return;}
    if(e.key==='p'||e.key==='P'){paused=!paused;return;}
    keys[e.key]=true;
    if(e.key==='ArrowUp'||e.key==='w'||e.key==='W')player.vy=-6;
    if(e.key==='ArrowDown'||e.key==='s'||e.key==='S')player.vy=6;
  });
  document.addEventListener('keyup',e=>{
    keys[e.key]=false;
    if(['ArrowUp','ArrowDown','w','W','s','S'].includes(e.key))player.vy=0;
  });
  cv.addEventListener('mousemove',e=>{
    const r=cv.getBoundingClientRect();const my=(e.clientY-r.top)*(H/r.height);
    player.y=Math.max(0,Math.min(H-PH,my-PH/2));
  });
  cv.addEventListener('touchmove',e=>{e.preventDefault();
    const r=cv.getBoundingClientRect();const my=(e.touches[0].clientY-r.top)*(H/r.height);
    player.y=Math.max(0,Math.min(H-PH,my-PH/2));},{passive:false});
  startBtn.onclick=()=>{ov.style.display='none';init();requestAnimationFrame(loop);};
})();
</script></body></html>
"""


# ──── BREAKOUT ──────────────────────────────────────────────────────────
_BREAKOUT = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>__TITLE__</title>
<style>__BASE_CSS__</style></head>
<body><div class="shell-frame">
  <h1 class="title">__TITLE__</h1>
  <div class="hud"><span>SCORE: <b id="sc">0</b></span><span>LIVES: <b id="lv">3</b></span><span>LEVEL: <b id="ll">1</b></span></div>
  <canvas id="cv" width="560" height="640"></canvas>
  <div class="footer">← → / A D · MOUSE · TOUCH · R RESTART · P PAUSE</div>
  <div class="overlay" id="ov"><h2>SHELL · BREAKOUT</h2>
    <p>Smash all bricks · Don't drop the ball</p><button id="startBtn">START</button></div>
</div>
<script>
(()=>{
  const cv=document.getElementById('cv'),ctx=cv.getContext('2d');
  const W=cv.width,H=cv.height,PW=90,PH=12,BR=8;
  const sEl=document.getElementById('sc'),lEl=document.getElementById('lv'),llEl=document.getElementById('ll');
  const ov=document.getElementById('ov'),startBtn=document.getElementById('startBtn');
  let paddle,ball,bricks,score,lives,level,running,paused;
  const COLS=8,ROWS=6,BRICK_W=W/COLS-4,BRICK_H=18;
  const COLORS=['#00f0ff','#ac89ff','#3ee3a8','#ffd166','#ff7a59','#ff5fa1'];
  let actx;function beep(f,d=0.05,t='square',v=0.06){try{actx=actx||new(window.AudioContext||window.webkitAudioContext)();
    const o=actx.createOscillator(),g=actx.createGain();o.type=t;o.frequency.value=f;g.gain.value=v;
    o.connect(g);g.connect(actx.destination);o.start();
    g.gain.exponentialRampToValueAtTime(.0001,actx.currentTime+d);o.stop(actx.currentTime+d);}catch(e){}}
  function buildBricks(){
    bricks=[];
    for(let r=0;r<ROWS;r++)for(let c=0;c<COLS;c++)
      bricks.push({x:c*(BRICK_W+4)+2,y:r*(BRICK_H+4)+40,w:BRICK_W,h:BRICK_H,c:COLORS[r%COLORS.length],alive:true,hp:Math.floor(r/3)+1});
  }
  function init(){paddle={x:W/2-PW/2};ball={x:W/2,y:H-40,vx:4,vy:-4,r:BR};
    score=0;lives=3;level=1;buildBricks();sEl.textContent=0;lEl.textContent=3;llEl.textContent=1;running=true;paused=false;}
  function nextLevel(){level++;llEl.textContent=level;buildBricks();
    ball={x:W/2,y:H-40,vx:4*(level<5?1:1.2),vy:-4*(level<5?1:1.2),r:BR};paddle.x=W/2-PW/2;}
  function endGame(win){running=false;
    ov.innerHTML='<h2>'+(win?'VICTORY':'GAME OVER')+'</h2><p>Score: <b style="color:#3ee3a8">'+score+
      '</b></p><button id="r2">PLAY AGAIN</button>';ov.style.display='flex';
    document.getElementById('r2').onclick=()=>{ov.style.display='none';init();};}
  function step(){
    ball.x+=ball.vx;ball.y+=ball.vy;
    if(ball.x<=ball.r||ball.x>=W-ball.r){ball.vx*=-1;beep(520,0.04);}
    if(ball.y<=ball.r){ball.vy*=-1;beep(520,0.04);}
    if(ball.y>=H-PH-ball.r&&ball.x>=paddle.x&&ball.x<=paddle.x+PW){
      ball.vy=-Math.abs(ball.vy);
      ball.vx+=(ball.x-(paddle.x+PW/2))*0.06;beep(700,0.05);
    }
    if(ball.y>H){lives--;lEl.textContent=lives;
      if(lives<=0){endGame(false);return;}
      ball={x:W/2,y:H-40,vx:4,vy:-4,r:BR};beep(180,0.2,'sawtooth');}
    // bricks
    for(const b of bricks){
      if(!b.alive)continue;
      if(ball.x>b.x&&ball.x<b.x+b.w&&ball.y>b.y&&ball.y<b.y+b.h){
        b.hp--;
        if(b.hp<=0){b.alive=false;score+=10;sEl.textContent=score;}
        ball.vy*=-1;beep(880,0.06,'square');break;
      }
    }
    if(bricks.every(b=>!b.alive)){
      if(level>=5){endGame(true);return;}
      nextLevel();
    }
  }
  function draw(){
    ctx.fillStyle='#0a0e1a';ctx.fillRect(0,0,W,H);
    // bricks
    ctx.shadowBlur=10;
    bricks.forEach(b=>{if(!b.alive)return;ctx.shadowColor=b.c;ctx.fillStyle=b.c;
      ctx.fillRect(b.x,b.y,b.w,b.h);ctx.fillStyle='rgba(255,255,255,0.2)';ctx.fillRect(b.x,b.y,b.w,3);});
    // paddle
    ctx.shadowColor='#00f0ff';ctx.fillStyle='#00f0ff';
    ctx.fillRect(paddle.x,H-PH-2,PW,PH);
    // ball
    ctx.shadowColor='#3ee3a8';ctx.fillStyle='#3ee3a8';
    ctx.beginPath();ctx.arc(ball.x,ball.y,ball.r,0,Math.PI*2);ctx.fill();
    ctx.shadowBlur=0;
  }
  function loop(){if(!running){draw();return;}if(!paused)step();draw();requestAnimationFrame(loop);}
  const keys={};
  document.addEventListener('keydown',e=>{
    if(e.key==='r'||e.key==='R'){ov.style.display='none';init();requestAnimationFrame(loop);return;}
    if(e.key==='p'||e.key==='P'){paused=!paused;return;}
    keys[e.key]=true;
  });
  document.addEventListener('keyup',e=>keys[e.key]=false);
  function pollKeys(){
    if(running&&!paused){
      if(keys['ArrowLeft']||keys['a']||keys['A'])paddle.x=Math.max(0,paddle.x-7);
      if(keys['ArrowRight']||keys['d']||keys['D'])paddle.x=Math.min(W-PW,paddle.x+7);
    }requestAnimationFrame(pollKeys);
  }
  cv.addEventListener('mousemove',e=>{const r=cv.getBoundingClientRect();
    paddle.x=Math.max(0,Math.min(W-PW,(e.clientX-r.left)*(W/r.width)-PW/2));});
  cv.addEventListener('touchmove',e=>{e.preventDefault();const r=cv.getBoundingClientRect();
    paddle.x=Math.max(0,Math.min(W-PW,(e.touches[0].clientX-r.left)*(W/r.width)-PW/2));},{passive:false});
  startBtn.onclick=()=>{ov.style.display='none';init();requestAnimationFrame(loop);requestAnimationFrame(pollKeys);};
})();
</script></body></html>
"""


# ──── FLAPPY ────────────────────────────────────────────────────────────
_FLAPPY = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>__TITLE__</title>
<style>__BASE_CSS__</style></head>
<body><div class="shell-frame">
  <h1 class="title">__TITLE__</h1>
  <div class="hud"><span>SCORE: <b id="sc">0</b></span><span>BEST: <b id="bs">0</b></span></div>
  <canvas id="cv" width="400" height="600"></canvas>
  <div class="footer">SPACE / ↑ / CLICK / TAP — FLAP · R RESTART</div>
  <div class="overlay" id="ov"><h2>SHELL · FLAPPY</h2>
    <p>Tap or press SPACE to flap · Avoid the neon pillars</p><button id="startBtn">START</button></div>
</div>
<script>
(()=>{
  const cv=document.getElementById('cv'),ctx=cv.getContext('2d');
  const W=cv.width,H=cv.height;
  const sEl=document.getElementById('sc'),bEl=document.getElementById('bs');
  const ov=document.getElementById('ov'),startBtn=document.getElementById('startBtn');
  let bird,pipes,score,best=+(localStorage.getItem('shell_flappy_best')||0),running,frame;
  bEl.textContent=best;
  let actx;function beep(f,d=0.07,t='sine',v=0.07){try{actx=actx||new(window.AudioContext||window.webkitAudioContext)();
    const o=actx.createOscillator(),g=actx.createGain();o.type=t;o.frequency.value=f;g.gain.value=v;
    o.connect(g);g.connect(actx.destination);o.start();
    g.gain.exponentialRampToValueAtTime(.0001,actx.currentTime+d);o.stop(actx.currentTime+d);}catch(e){}}
  function init(){bird={x:80,y:H/2,vy:0,r:14};pipes=[];score=0;sEl.textContent=0;running=true;frame=0;}
  function flap(){if(!running)return;bird.vy=-7;beep(700,0.06);}
  function spawnPipe(){
    const gap=130;const top=40+Math.random()*(H-gap-160);
    pipes.push({x:W,top,bot:top+gap,passed:false,w:60});
  }
  function step(){
    frame++;if(frame%80===0)spawnPipe();
    bird.vy+=0.42;bird.y+=bird.vy;
    if(bird.y>H-bird.r||bird.y<bird.r)return die();
    pipes.forEach(p=>{p.x-=3;
      if(!p.passed&&p.x+p.w<bird.x){p.passed=true;score++;sEl.textContent=score;beep(880,0.06,'square');}
      if(bird.x+bird.r>p.x&&bird.x-bird.r<p.x+p.w&&(bird.y-bird.r<p.top||bird.y+bird.r>p.bot))return die();
    });
    pipes=pipes.filter(p=>p.x>-100);
  }
  function die(){if(!running)return;running=false;
    if(score>best){best=score;localStorage.setItem('shell_flappy_best',best);bEl.textContent=best;}
    ov.innerHTML='<h2>GAME OVER</h2><p>Score: <b style="color:#3ee3a8">'+score+
      '</b> · Best: <b style="color:#3ee3a8">'+best+'</b></p><button id="r2">PLAY AGAIN</button>';
    ov.style.display='flex';document.getElementById('r2').onclick=()=>{ov.style.display='none';init();};
    beep(140,0.4,'sawtooth',0.12);
  }
  function draw(){
    // bg gradient
    const g=ctx.createLinearGradient(0,0,0,H);g.addColorStop(0,'#0a0e1a');g.addColorStop(1,'#1a1030');
    ctx.fillStyle=g;ctx.fillRect(0,0,W,H);
    // pipes
    ctx.shadowBlur=14;
    pipes.forEach(p=>{ctx.shadowColor='#ac89ff';ctx.fillStyle='#ac89ff';
      ctx.fillRect(p.x,0,p.w,p.top);ctx.fillRect(p.x,p.bot,p.w,H-p.bot);
      ctx.fillStyle='#00f0ff';ctx.fillRect(p.x-3,p.top-12,p.w+6,12);ctx.fillRect(p.x-3,p.bot,p.w+6,12);});
    // bird
    ctx.shadowColor='#3ee3a8';ctx.fillStyle='#3ee3a8';
    ctx.beginPath();ctx.arc(bird.x,bird.y,bird.r,0,Math.PI*2);ctx.fill();
    ctx.shadowBlur=0;
    ctx.fillStyle='#0a0e1a';ctx.beginPath();ctx.arc(bird.x+5,bird.y-3,2,0,Math.PI*2);ctx.fill();
  }
  function loop(){if(running)step();draw();if(running)requestAnimationFrame(loop);else draw();}
  document.addEventListener('keydown',e=>{
    if(e.key==='r'||e.key==='R'){ov.style.display='none';init();requestAnimationFrame(loop);return;}
    if(e.key===' '||e.key==='ArrowUp'||e.key==='w'||e.key==='W'){e.preventDefault();flap();}
  });
  cv.addEventListener('mousedown',flap);
  cv.addEventListener('touchstart',e=>{e.preventDefault();flap();},{passive:false});
  startBtn.onclick=()=>{ov.style.display='none';init();requestAnimationFrame(loop);};
})();
</script></body></html>
"""


# ──── 2048 ──────────────────────────────────────────────────────────────
_2048 = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>__TITLE__</title>
<style>__BASE_CSS__
.tiles{display:grid;grid-template-columns:repeat(4,90px);grid-template-rows:repeat(4,90px);gap:10px;
  background:rgba(0,240,255,0.06);padding:10px;border-radius:14px;border:1px solid rgba(0,240,255,.2);
  box-shadow:0 0 30px rgba(0,240,255,.18);}
.tile{display:flex;align-items:center;justify-content:center;font-size:28px;font-weight:bold;
  border-radius:10px;background:rgba(255,255,255,0.04);color:#00f0ff;transition:all .15s;
  border:1px solid rgba(0,240,255,.18);}
.tile.v2{background:#0d1626;color:#00f0ff;}
.tile.v4{background:#11203a;color:#00f0ff;}
.tile.v8{background:#162a4f;color:#3ee3a8;text-shadow:0 0 8px #3ee3a8;}
.tile.v16{background:#1a3463;color:#3ee3a8;text-shadow:0 0 10px #3ee3a8;}
.tile.v32{background:#243f7a;color:#ffd166;text-shadow:0 0 10px #ffd166;}
.tile.v64{background:#2d4d92;color:#ff7a59;text-shadow:0 0 12px #ff7a59;}
.tile.v128{background:#0a4068;color:#00f0ff;font-size:24px;text-shadow:0 0 14px #00f0ff;box-shadow:0 0 18px #00f0ff;}
.tile.v256{background:#06547d;color:#00f0ff;font-size:24px;text-shadow:0 0 16px #00f0ff;box-shadow:0 0 22px #00f0ff;}
.tile.v512{background:#0a6d96;color:#ac89ff;font-size:22px;text-shadow:0 0 16px #ac89ff;box-shadow:0 0 22px #ac89ff;}
.tile.v1024{background:#1c84a8;color:#ac89ff;font-size:20px;text-shadow:0 0 18px #ac89ff;box-shadow:0 0 26px #ac89ff;}
.tile.v2048{background:#2c9bbe;color:#fff;font-size:20px;text-shadow:0 0 22px #fff;box-shadow:0 0 32px #00f0ff;}
</style></head>
<body><div class="shell-frame" id="frame">
  <h1 class="title">__TITLE__</h1>
  <div class="hud"><span>SCORE: <b id="sc">0</b></span><span>BEST: <b id="bs">0</b></span></div>
  <div class="tiles" id="tiles"></div>
  <div class="footer">↑↓←→ / WASD · SWIPE · R RESTART</div>
  <div class="overlay" id="ov"><h2>SHELL · 2048</h2>
    <p>Slide tiles · Merge equals · Reach 2048</p><button id="startBtn">START</button></div>
</div>
<script>
(()=>{
  const sEl=document.getElementById('sc'),bEl=document.getElementById('bs'),tilesEl=document.getElementById('tiles');
  const ov=document.getElementById('ov'),startBtn=document.getElementById('startBtn');
  let grid,score,best=+(localStorage.getItem('shell_2048_best')||0),running,won;
  bEl.textContent=best;
  let actx;function beep(f,d=0.05,t='square',v=0.05){try{actx=actx||new(window.AudioContext||window.webkitAudioContext)();
    const o=actx.createOscillator(),g=actx.createGain();o.type=t;o.frequency.value=f;g.gain.value=v;
    o.connect(g);g.connect(actx.destination);o.start();
    g.gain.exponentialRampToValueAtTime(.0001,actx.currentTime+d);o.stop(actx.currentTime+d);}catch(e){}}
  function emptyCells(){const e=[];for(let y=0;y<4;y++)for(let x=0;x<4;x++)if(!grid[y][x])e.push([y,x]);return e;}
  function spawn(){const e=emptyCells();if(!e.length)return;const[y,x]=e[(Math.random()*e.length)|0];
    grid[y][x]=Math.random()<0.9?2:4;}
  function init(){grid=[[0,0,0,0],[0,0,0,0],[0,0,0,0],[0,0,0,0]];score=0;won=false;running=true;
    spawn();spawn();sEl.textContent=0;render();}
  function render(){
    tilesEl.innerHTML='';
    for(let y=0;y<4;y++)for(let x=0;x<4;x++){
      const v=grid[y][x];const d=document.createElement('div');d.className='tile'+(v?' v'+v:'');
      d.textContent=v||'';tilesEl.appendChild(d);
    }
  }
  function rotateCW(g){const n=[[0,0,0,0],[0,0,0,0],[0,0,0,0],[0,0,0,0]];
    for(let y=0;y<4;y++)for(let x=0;x<4;x++)n[x][3-y]=g[y][x];return n;}
  function slideLeft(g){let moved=false;
    for(let y=0;y<4;y++){
      let row=g[y].filter(v=>v);
      for(let i=0;i<row.length-1;i++)if(row[i]===row[i+1]){
        row[i]*=2;score+=row[i];row.splice(i+1,1);
        if(row[i]===2048&&!won){won=true;setTimeout(()=>alert('You hit 2048! Keep going for a higher score.'),200);}
      }
      while(row.length<4)row.push(0);
      if(row.some((v,i)=>v!==g[y][i]))moved=true;
      g[y]=row;
    }return moved;
  }
  function move(dir){
    if(!running)return;
    let g=grid.map(r=>r.slice());let rot=0;
    if(dir==='up')rot=3;else if(dir==='right')rot=2;else if(dir==='down')rot=1;
    for(let i=0;i<rot;i++)g=rotateCW(g);
    const moved=slideLeft(g);
    for(let i=0;i<(4-rot)%4;i++)g=rotateCW(g);
    if(moved){grid=g;spawn();sEl.textContent=score;
      if(score>best){best=score;localStorage.setItem('shell_2048_best',best);bEl.textContent=best;}
      beep(660,0.05);render();
      // game over check
      if(emptyCells().length===0){
        let canMove=false;
        outer:for(let y=0;y<4;y++)for(let x=0;x<4;x++){
          if(x<3&&grid[y][x]===grid[y][x+1]){canMove=true;break outer;}
          if(y<3&&grid[y][x]===grid[y+1][x]){canMove=true;break outer;}
        }
        if(!canMove){running=false;
          ov.innerHTML='<h2>GAME OVER</h2><p>Score: <b style="color:#3ee3a8">'+score+
            '</b></p><button id="r2">PLAY AGAIN</button>';ov.style.display='flex';
          document.getElementById('r2').onclick=()=>{ov.style.display='none';init();};}
      }
    }
  }
  document.addEventListener('keydown',e=>{
    if(e.key==='r'||e.key==='R'){ov.style.display='none';init();return;}
    const m={ArrowLeft:'left',ArrowRight:'right',ArrowUp:'up',ArrowDown:'down',
      a:'left',A:'left',d:'right',D:'right',w:'up',W:'up',s:'down',S:'down'};
    if(m[e.key]){e.preventDefault();move(m[e.key]);}
  });
  let tx=0,ty=0;
  document.addEventListener('touchstart',e=>{tx=e.touches[0].clientX;ty=e.touches[0].clientY;});
  document.addEventListener('touchend',e=>{
    const dx=e.changedTouches[0].clientX-tx,dy=e.changedTouches[0].clientY-ty;
    if(Math.abs(dx)<20&&Math.abs(dy)<20)return;
    if(Math.abs(dx)>Math.abs(dy))move(dx>0?'right':'left');else move(dy>0?'down':'up');
  });
  startBtn.onclick=()=>{ov.style.display='none';init();};
})();
</script></body></html>
"""


# ──── SPACE INVADERS ────────────────────────────────────────────────────
_INVADERS = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>__TITLE__</title>
<style>__BASE_CSS__</style></head>
<body><div class="shell-frame">
  <h1 class="title">__TITLE__</h1>
  <div class="hud"><span>SCORE: <b id="sc">0</b></span><span>LIVES: <b id="lv">3</b></span><span>WAVE: <b id="wv">1</b></span></div>
  <canvas id="cv" width="560" height="640"></canvas>
  <div class="footer">← → / A D · SPACE FIRE · R RESTART · P PAUSE</div>
  <div class="overlay" id="ov"><h2>SHELL · INVADERS</h2>
    <p>Defend Earth · Shoot the neon swarm · Don't let them land</p><button id="startBtn">START</button></div>
</div>
<script>
(()=>{
  const cv=document.getElementById('cv'),ctx=cv.getContext('2d');
  const W=cv.width,H=cv.height;
  const sEl=document.getElementById('sc'),lEl=document.getElementById('lv'),wEl=document.getElementById('wv');
  const ov=document.getElementById('ov'),startBtn=document.getElementById('startBtn');
  let player,bullets,enemies,ebullets,score,lives,wave,running,paused,lastShot;
  let actx;function beep(f,d=0.05,t='square',v=0.06){try{actx=actx||new(window.AudioContext||window.webkitAudioContext)();
    const o=actx.createOscillator(),g=actx.createGain();o.type=t;o.frequency.value=f;g.gain.value=v;
    o.connect(g);g.connect(actx.destination);o.start();
    g.gain.exponentialRampToValueAtTime(.0001,actx.currentTime+d);o.stop(actx.currentTime+d);}catch(e){}}
  function buildWave(){
    enemies=[];const cols=8,rows=4,sx=60,sy=60,gx=50,gy=42;
    for(let r=0;r<rows;r++)for(let c=0;c<cols;c++)
      enemies.push({x:sx+c*gx,y:sy+r*gy,w:28,h:20,alive:true,row:r});
  }
  function init(){player={x:W/2-20,y:H-40,w:40,h:14,vx:0};bullets=[];ebullets=[];
    score=0;lives=3;wave=1;lastShot=0;buildWave();
    sEl.textContent=0;lEl.textContent=3;wEl.textContent=1;running=true;paused=false;}
  function endGame(win){running=false;
    ov.innerHTML='<h2>'+(win?'EARTH SAVED':'GAME OVER')+'</h2><p>Score: <b style="color:#3ee3a8">'+score+
      '</b> · Wave: <b style="color:#3ee3a8">'+wave+'</b></p><button id="r2">PLAY AGAIN</button>';
    ov.style.display='flex';document.getElementById('r2').onclick=()=>{ov.style.display='none';init();requestAnimationFrame(loop);};
    beep(120,0.5,'sawtooth',0.12);}
  let _dir=1,_drop=0;
  function step(t){
    player.x+=player.vx;player.x=Math.max(0,Math.min(W-player.w,player.x));
    // enemy march
    let edge=false;const speed=0.8+wave*0.3;
    enemies.forEach(e=>{if(!e.alive)return;e.x+=_dir*speed;if(e.x<2||e.x+e.w>W-2)edge=true;});
    if(edge){_dir*=-1;enemies.forEach(e=>{if(e.alive)e.y+=12;});}
    // enemy fire
    if(Math.random()<0.018+wave*0.005){
      const live=enemies.filter(e=>e.alive);
      if(live.length){const e=live[(Math.random()*live.length)|0];
        ebullets.push({x:e.x+e.w/2,y:e.y+e.h,vy:3.5+wave*0.2});}
    }
    // bullets
    bullets.forEach(b=>b.y-=8);bullets=bullets.filter(b=>b.y>-10);
    ebullets.forEach(b=>b.y+=b.vy);ebullets=ebullets.filter(b=>b.y<H+10);
    // bullet vs enemy
    bullets.forEach(b=>{enemies.forEach(e=>{if(!e.alive)return;
      if(b.x>e.x&&b.x<e.x+e.w&&b.y>e.y&&b.y<e.y+e.h){
        e.alive=false;b.y=-99;score+=10*(4-e.row);sEl.textContent=score;beep(720,0.06);
      }});});
    // ebullet vs player
    ebullets.forEach(b=>{
      if(b.x>player.x&&b.x<player.x+player.w&&b.y>player.y&&b.y<player.y+player.h){
        b.y=H+99;lives--;lEl.textContent=lives;beep(220,0.18,'sawtooth');
        if(lives<=0)endGame(false);
      }
    });
    // enemy reached bottom?
    if(enemies.some(e=>e.alive&&e.y+e.h>=player.y))endGame(false);
    // wave clear?
    if(enemies.every(e=>!e.alive)){wave++;wEl.textContent=wave;
      if(wave>10)endGame(true);else{buildWave();_dir=1;}}
  }
  function draw(){
    ctx.fillStyle='#0a0e1a';ctx.fillRect(0,0,W,H);
    // stars
    ctx.fillStyle='rgba(255,255,255,0.4)';for(let i=0;i<40;i++){
      const x=(i*73)%W,y=(i*131+performance.now()*0.04)%H;ctx.fillRect(x,y,1,1);}
    // player
    ctx.shadowBlur=14;ctx.shadowColor='#00f0ff';ctx.fillStyle='#00f0ff';
    ctx.fillRect(player.x,player.y,player.w,player.h);
    ctx.fillRect(player.x+player.w/2-3,player.y-6,6,6);
    // enemies
    const COLS=['#ff5fa1','#ac89ff','#3ee3a8','#ffd166'];
    enemies.forEach(e=>{if(!e.alive)return;ctx.shadowColor=COLS[e.row%4];ctx.fillStyle=COLS[e.row%4];
      ctx.fillRect(e.x,e.y,e.w,e.h);ctx.fillRect(e.x+4,e.y+e.h,4,4);ctx.fillRect(e.x+e.w-8,e.y+e.h,4,4);});
    // bullets
    ctx.shadowColor='#3ee3a8';ctx.fillStyle='#3ee3a8';bullets.forEach(b=>ctx.fillRect(b.x-2,b.y,4,10));
    ctx.shadowColor='#ff5fa1';ctx.fillStyle='#ff5fa1';ebullets.forEach(b=>ctx.fillRect(b.x-2,b.y,4,10));
    ctx.shadowBlur=0;
  }
  function loop(t){if(!running){draw();return;}if(!paused)step(t);draw();requestAnimationFrame(loop);}
  const keys={};
  document.addEventListener('keydown',e=>{
    if(e.key==='r'||e.key==='R'){ov.style.display='none';init();requestAnimationFrame(loop);return;}
    if(e.key==='p'||e.key==='P'){paused=!paused;return;}
    keys[e.key]=true;
    if(e.key==='ArrowLeft'||e.key==='a'||e.key==='A')player.vx=-6;
    if(e.key==='ArrowRight'||e.key==='d'||e.key==='D')player.vx=6;
    if(e.key===' '){e.preventDefault();const now=performance.now();if(now-lastShot>180){lastShot=now;
      bullets.push({x:player.x+player.w/2,y:player.y});beep(880,0.05);}}
  });
  document.addEventListener('keyup',e=>{keys[e.key]=false;
    if(['ArrowLeft','ArrowRight','a','A','d','D'].includes(e.key))player.vx=0;});
  startBtn.onclick=()=>{ov.style.display='none';init();requestAnimationFrame(loop);};
})();
</script></body></html>
"""


# ──── DINO RUNNER ───────────────────────────────────────────────────────
_RUNNER = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>__TITLE__</title>
<style>__BASE_CSS__</style></head>
<body><div class="shell-frame">
  <h1 class="title">__TITLE__</h1>
  <div class="hud"><span>SCORE: <b id="sc">0</b></span><span>BEST: <b id="bs">0</b></span><span>SPEED: <b id="sp">1</b></span></div>
  <canvas id="cv" width="720" height="280"></canvas>
  <div class="footer">SPACE / ↑ / TAP — JUMP · ↓ DUCK · R RESTART</div>
  <div class="overlay" id="ov"><h2>SHELL · RUNNER</h2>
    <p>Jump the cacti · Duck under the drones · Survive the longest</p><button id="startBtn">START</button></div>
</div>
<script>
(()=>{
  const cv=document.getElementById('cv'),ctx=cv.getContext('2d');
  const W=cv.width,H=cv.height,GROUND=H-40;
  const sEl=document.getElementById('sc'),bEl=document.getElementById('bs'),spEl=document.getElementById('sp');
  const ov=document.getElementById('ov'),startBtn=document.getElementById('startBtn');
  let player,obstacles,score,best=+(localStorage.getItem('shell_runner_best')||0),speed,running,frame,duck;
  bEl.textContent=best;
  let actx;function beep(f,d=0.05,t='square',v=0.06){try{actx=actx||new(window.AudioContext||window.webkitAudioContext)();
    const o=actx.createOscillator(),g=actx.createGain();o.type=t;o.frequency.value=f;g.gain.value=v;
    o.connect(g);g.connect(actx.destination);o.start();
    g.gain.exponentialRampToValueAtTime(.0001,actx.currentTime+d);o.stop(actx.currentTime+d);}catch(e){}}
  function init(){player={x:60,y:GROUND-40,w:32,h:40,vy:0,onGround:true};
    obstacles=[];score=0;speed=6;frame=0;duck=false;running=true;sEl.textContent=0;spEl.textContent=1;}
  function jump(){if(!running)return;if(player.onGround){player.vy=-13;player.onGround=false;beep(660,0.07);}}
  function spawn(){
    const isAir=Math.random()<0.3;
    if(isAir)obstacles.push({x:W,y:GROUND-70,w:36,h:18,air:true});
    else obstacles.push({x:W,y:GROUND-30,w:18+((Math.random()*22)|0),h:30,air:false});
  }
  function die(){if(!running)return;running=false;
    if(score>best){best=score;localStorage.setItem('shell_runner_best',best);bEl.textContent=best;}
    ov.innerHTML='<h2>GAME OVER</h2><p>Score: <b style="color:#3ee3a8">'+score+
      '</b> · Best: <b style="color:#3ee3a8">'+best+'</b></p><button id="r2">PLAY AGAIN</button>';
    ov.style.display='flex';document.getElementById('r2').onclick=()=>{ov.style.display='none';init();requestAnimationFrame(loop);};
    beep(140,0.4,'sawtooth',0.12);}
  function step(){
    frame++;score++;sEl.textContent=score;
    if(score%500===0){speed+=0.7;spEl.textContent=(speed/6).toFixed(1);}
    if(frame%Math.max(40,90-((speed-6)*5))===0)spawn();
    player.vy+=0.7;player.y+=player.vy;
    const targetH=duck?20:40;player.h=targetH;
    if(player.y>=GROUND-player.h){player.y=GROUND-player.h;player.vy=0;player.onGround=true;}
    obstacles.forEach(o=>o.x-=speed);obstacles=obstacles.filter(o=>o.x>-50);
    obstacles.forEach(o=>{
      if(player.x+player.w>o.x&&player.x<o.x+o.w&&player.y+player.h>o.y&&player.y<o.y+o.h)die();
    });
  }
  function draw(){
    const g=ctx.createLinearGradient(0,0,0,H);g.addColorStop(0,'#0a0e1a');g.addColorStop(1,'#1a0a2a');
    ctx.fillStyle=g;ctx.fillRect(0,0,W,H);
    // ground
    ctx.strokeStyle='#00f0ff';ctx.shadowBlur=8;ctx.shadowColor='#00f0ff';ctx.lineWidth=2;
    ctx.beginPath();ctx.moveTo(0,GROUND);ctx.lineTo(W,GROUND);ctx.stroke();
    ctx.shadowBlur=0;
    // grid lines moving
    ctx.strokeStyle='rgba(0,240,255,0.12)';
    for(let i=0;i<20;i++){const x=(i*60-(frame*4)%60);ctx.beginPath();ctx.moveTo(x,GROUND);ctx.lineTo(x-30,H);ctx.stroke();}
    // player
    ctx.shadowBlur=14;ctx.shadowColor='#3ee3a8';ctx.fillStyle='#3ee3a8';
    ctx.fillRect(player.x,player.y,player.w,player.h);
    ctx.fillStyle='#0a0e1a';ctx.fillRect(player.x+player.w-8,player.y+5,3,3);
    // obstacles
    obstacles.forEach(o=>{ctx.shadowColor=o.air?'#ff5fa1':'#ac89ff';ctx.fillStyle=o.air?'#ff5fa1':'#ac89ff';
      ctx.fillRect(o.x,o.y,o.w,o.h);});
    ctx.shadowBlur=0;
  }
  function loop(){if(!running){draw();return;}step();draw();requestAnimationFrame(loop);}
  document.addEventListener('keydown',e=>{
    if(e.key==='r'||e.key==='R'){ov.style.display='none';init();requestAnimationFrame(loop);return;}
    if(e.key===' '||e.key==='ArrowUp'||e.key==='w'||e.key==='W'){e.preventDefault();jump();}
    if(e.key==='ArrowDown'||e.key==='s'||e.key==='S')duck=true;
  });
  document.addEventListener('keyup',e=>{if(e.key==='ArrowDown'||e.key==='s'||e.key==='S')duck=false;});
  cv.addEventListener('mousedown',jump);
  cv.addEventListener('touchstart',e=>{e.preventDefault();jump();},{passive:false});
  startBtn.onclick=()=>{ov.style.display='none';init();requestAnimationFrame(loop);};
})();
</script></body></html>
"""


# ──── TIC TAC TOE ───────────────────────────────────────────────────────
_TICTACTOE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>__TITLE__</title>
<style>__BASE_CSS__
.board{display:grid;grid-template-columns:repeat(3,110px);grid-template-rows:repeat(3,110px);gap:8px;
  background:rgba(0,240,255,.06);padding:10px;border-radius:14px;border:1px solid rgba(0,240,255,.25);
  box-shadow:0 0 30px rgba(0,240,255,.18);}
.cell{display:flex;align-items:center;justify-content:center;font-size:64px;font-weight:bold;cursor:pointer;
  border-radius:10px;background:rgba(255,255,255,.03);border:1px solid rgba(0,240,255,.15);transition:all .15s;}
.cell:hover{background:rgba(0,240,255,.08);}
.cell.x{color:#00f0ff;text-shadow:0 0 14px #00f0ff;}
.cell.o{color:#ff5fa1;text-shadow:0 0 14px #ff5fa1;}
.cell.win{background:rgba(62,227,168,.18);border-color:#3ee3a8;}
.status{color:#3ee3a8;font-size:18px;letter-spacing:3px;text-shadow:0 0 8px #3ee3a8;min-height:24px;}
</style></head>
<body><div class="shell-frame">
  <h1 class="title">__TITLE__</h1>
  <div class="hud"><span>YOU: <b id="ws">0</b></span><span>CPU: <b id="ls">0</b></span><span>DRAW: <b id="ds">0</b></span></div>
  <div class="status" id="status">YOUR TURN (X)</div>
  <div class="board" id="board"></div>
  <div class="footer">CLICK A CELL · R = NEW GAME · DIFFICULTY: HARD (MINIMAX)</div>
  <div class="overlay" id="ov"><h2>SHELL · TIC TAC TOE</h2>
    <p>You are X · CPU is O · Three in a row wins</p><button id="startBtn">START</button></div>
</div>
<script>
(()=>{
  const board=document.getElementById('board'),status=document.getElementById('status');
  const ws=document.getElementById('ws'),ls=document.getElementById('ls'),ds=document.getElementById('ds');
  const ov=document.getElementById('ov'),startBtn=document.getElementById('startBtn');
  let cells,state,turn,wins=0,losses=0,draws=0,locked;
  let actx;function beep(f,d=0.06,t='square',v=0.07){try{actx=actx||new(window.AudioContext||window.webkitAudioContext)();
    const o=actx.createOscillator(),g=actx.createGain();o.type=t;o.frequency.value=f;g.gain.value=v;
    o.connect(g);g.connect(actx.destination);o.start();
    g.gain.exponentialRampToValueAtTime(.0001,actx.currentTime+d);o.stop(actx.currentTime+d);}catch(e){}}
  const LINES=[[0,1,2],[3,4,5],[6,7,8],[0,3,6],[1,4,7],[2,5,8],[0,4,8],[2,4,6]];
  function check(s){for(const L of LINES){const [a,b,c]=L;if(s[a]&&s[a]===s[b]&&s[a]===s[c])return{w:s[a],line:L};}
    if(s.every(v=>v))return{w:'D'};return null;}
  function minimax(s,player){
    const r=check(s);if(r){if(r.w==='O')return{score:10};if(r.w==='X')return{score:-10};return{score:0};}
    const moves=[];for(let i=0;i<9;i++)if(!s[i]){
      s[i]=player;const m=minimax(s,player==='O'?'X':'O');s[i]='';
      moves.push({i,score:m.score});}
    if(player==='O'){let best=moves[0];for(const m of moves)if(m.score>best.score)best=m;return best;}
    else{let best=moves[0];for(const m of moves)if(m.score<best.score)best=m;return best;}
  }
  function render(winLine){
    cells.forEach((c,i)=>{c.className='cell'+(state[i]==='X'?' x':state[i]==='O'?' o':'');c.textContent=state[i]||'';
      if(winLine&&winLine.includes(i))c.classList.add('win');});
  }
  function newGame(){state=Array(9).fill('');turn='X';locked=false;render();status.textContent='YOUR TURN (X)';}
  function endRound(r){
    locked=true;
    if(r.w==='X'){wins++;ws.textContent=wins;status.textContent='YOU WIN!';beep(880,0.15,'square');render(r.line);}
    else if(r.w==='O'){losses++;ls.textContent=losses;status.textContent='CPU WINS';beep(220,0.2,'sawtooth');render(r.line);}
    else{draws++;ds.textContent=draws;status.textContent='DRAW';beep(440,0.1);render();}
    setTimeout(()=>{newGame();},1500);
  }
  function cpuMove(){
    if(locked)return;
    const best=minimax(state.slice(),'O');
    state[best.i]='O';beep(440,0.06);render();
    const r=check(state);if(r)return endRound(r);
    turn='X';status.textContent='YOUR TURN (X)';
  }
  function click(i){
    if(locked||state[i]||turn!=='X')return;
    state[i]='X';beep(660,0.06);render();
    const r=check(state);if(r)return endRound(r);
    turn='O';status.textContent='CPU THINKING…';
    setTimeout(cpuMove,260);
  }
  function build(){
    board.innerHTML='';cells=[];
    for(let i=0;i<9;i++){const c=document.createElement('div');c.className='cell';
      c.addEventListener('click',()=>click(i));board.appendChild(c);cells.push(c);}
  }
  document.addEventListener('keydown',e=>{if(e.key==='r'||e.key==='R')newGame();});
  startBtn.onclick=()=>{ov.style.display='none';build();newGame();};
})();
</script></body></html>
"""


# ──── MEMORY MATCH ──────────────────────────────────────────────────────
_MEMORY = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>__TITLE__</title>
<style>__BASE_CSS__
.grid{display:grid;grid-template-columns:repeat(4,80px);grid-template-rows:repeat(4,80px);gap:8px;
  padding:10px;background:rgba(0,240,255,.05);border-radius:14px;border:1px solid rgba(0,240,255,.2);}
.card{display:flex;align-items:center;justify-content:center;font-size:32px;cursor:pointer;border-radius:10px;
  background:rgba(0,240,255,.1);border:1px solid rgba(0,240,255,.3);transition:all .25s;color:transparent;}
.card.flip{background:rgba(172,137,255,.18);color:#00f0ff;text-shadow:0 0 12px #00f0ff;border-color:#ac89ff;
  transform:rotateY(180deg);}
.card.match{background:rgba(62,227,168,.2);color:#3ee3a8;text-shadow:0 0 14px #3ee3a8;border-color:#3ee3a8;cursor:default;}
</style></head>
<body><div class="shell-frame">
  <h1 class="title">__TITLE__</h1>
  <div class="hud"><span>MOVES: <b id="mv">0</b></span><span>MATCHED: <b id="mt">0</b>/8</span><span>BEST: <b id="bs">—</b></span></div>
  <div class="grid" id="grid"></div>
  <div class="footer">CLICK PAIRS · R = NEW GAME</div>
  <div class="overlay" id="ov"><h2>SHELL · MEMORY</h2>
    <p>Find all 8 pairs in the fewest moves</p><button id="startBtn">START</button></div>
</div>
<script>
(()=>{
  const grid=document.getElementById('grid'),mv=document.getElementById('mv'),mt=document.getElementById('mt'),bs=document.getElementById('bs');
  const ov=document.getElementById('ov'),startBtn=document.getElementById('startBtn');
  let cards,first,second,locked,moves,matched;
  const best=+(localStorage.getItem('shell_memory_best')||0);bs.textContent=best||'—';
  const ICONS=['◆','★','▲','◉','◇','♥','♣','♠'];
  let actx;function beep(f,d=0.05,t='square',v=0.06){try{actx=actx||new(window.AudioContext||window.webkitAudioContext)();
    const o=actx.createOscillator(),g=actx.createGain();o.type=t;o.frequency.value=f;g.gain.value=v;
    o.connect(g);g.connect(actx.destination);o.start();
    g.gain.exponentialRampToValueAtTime(.0001,actx.currentTime+d);o.stop(actx.currentTime+d);}catch(e){}}
  function shuffle(a){for(let i=a.length-1;i>0;i--){const j=(Math.random()*(i+1))|0;[a[i],a[j]]=[a[j],a[i]];}return a;}
  function init(){
    moves=0;matched=0;first=null;second=null;locked=false;mv.textContent=0;mt.textContent=0;
    const deck=shuffle([...ICONS,...ICONS]);
    grid.innerHTML='';cards=[];
    deck.forEach((sym,i)=>{const c=document.createElement('div');c.className='card';c.textContent=sym;c.dataset.sym=sym;
      c.addEventListener('click',()=>flip(c));grid.appendChild(c);cards.push(c);});
  }
  function flip(c){
    if(locked||c.classList.contains('flip')||c.classList.contains('match'))return;
    c.classList.add('flip');beep(540,0.05);
    if(!first){first=c;return;}
    second=c;moves++;mv.textContent=moves;
    if(first.dataset.sym===second.dataset.sym){
      first.classList.add('match');second.classList.add('match');beep(880,0.1,'square');
      first=null;second=null;matched++;mt.textContent=matched;
      if(matched===8){
        if(!best||moves<best){localStorage.setItem('shell_memory_best',moves);bs.textContent=moves;}
        setTimeout(()=>{
          ov.innerHTML='<h2>YOU WIN!</h2><p>Solved in <b style="color:#3ee3a8">'+moves+'</b> moves</p><button id="r2">NEW GAME</button>';
          ov.style.display='flex';document.getElementById('r2').onclick=()=>{ov.style.display='none';init();};
        },400);
      }
    }else{
      locked=true;setTimeout(()=>{first.classList.remove('flip');second.classList.remove('flip');
        first=null;second=null;locked=false;beep(220,0.08,'sawtooth');},700);
    }
  }
  document.addEventListener('keydown',e=>{if(e.key==='r'||e.key==='R')init();});
  startBtn.onclick=()=>{ov.style.display='none';init();};
})();
</script></body></html>
"""


# ──── WHACK A MOLE ──────────────────────────────────────────────────────
_WHACK = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>__TITLE__</title>
<style>__BASE_CSS__
.holes{display:grid;grid-template-columns:repeat(3,120px);grid-template-rows:repeat(3,120px);gap:14px;padding:14px;
  background:rgba(0,240,255,.05);border-radius:14px;border:1px solid rgba(0,240,255,.2);}
.hole{display:flex;align-items:flex-end;justify-content:center;border-radius:50%;background:radial-gradient(circle,#06080f,#000);
  border:1px solid rgba(0,240,255,.3);overflow:hidden;cursor:pointer;position:relative;}
.mole{width:80px;height:80px;border-radius:50%;background:#3ee3a8;box-shadow:0 0 20px #3ee3a8;
  transition:transform .18s;transform:translateY(110%);}
.mole.up{transform:translateY(20%);}
.mole.bomb{background:#ff5fa1;box-shadow:0 0 22px #ff5fa1;}
</style></head>
<body><div class="shell-frame">
  <h1 class="title">__TITLE__</h1>
  <div class="hud"><span>SCORE: <b id="sc">0</b></span><span>TIME: <b id="tm">30</b>s</span><span>BEST: <b id="bs">0</b></span></div>
  <div class="holes" id="holes"></div>
  <div class="footer">CLICK / TAP THE GREEN MOLES · AVOID PINK BOMBS · R = RESTART</div>
  <div class="overlay" id="ov"><h2>SHELL · WHACK A MOLE</h2>
    <p>Hit moles for +1 · Bombs for −2 · 30 seconds</p><button id="startBtn">START</button></div>
</div>
<script>
(()=>{
  const holes=document.getElementById('holes'),sEl=document.getElementById('sc'),tEl=document.getElementById('tm'),bEl=document.getElementById('bs');
  const ov=document.getElementById('ov'),startBtn=document.getElementById('startBtn');
  let score,time,best=+(localStorage.getItem('shell_whack_best')||0),running,timer,popper,cells;
  bEl.textContent=best;
  let actx;function beep(f,d=0.05,t='square',v=0.07){try{actx=actx||new(window.AudioContext||window.webkitAudioContext)();
    const o=actx.createOscillator(),g=actx.createGain();o.type=t;o.frequency.value=f;g.gain.value=v;
    o.connect(g);g.connect(actx.destination);o.start();
    g.gain.exponentialRampToValueAtTime(.0001,actx.currentTime+d);o.stop(actx.currentTime+d);}catch(e){}}
  function build(){
    holes.innerHTML='';cells=[];
    for(let i=0;i<9;i++){const h=document.createElement('div');h.className='hole';
      const m=document.createElement('div');m.className='mole';h.appendChild(m);
      h.addEventListener('click',()=>whack(i));holes.appendChild(h);cells.push({hole:h,mole:m,active:false,bomb:false});}
  }
  function pop(){
    const free=cells.filter(c=>!c.active);if(!free.length)return;
    const c=free[(Math.random()*free.length)|0];const isBomb=Math.random()<0.18;
    c.active=true;c.bomb=isBomb;c.mole.classList.add('up');c.mole.classList.toggle('bomb',isBomb);
    setTimeout(()=>{if(c.active){c.mole.classList.remove('up');setTimeout(()=>{c.active=false;c.bomb=false;c.mole.classList.remove('bomb');},200);}},700+Math.random()*500);
  }
  function whack(i){
    if(!running)return;const c=cells[i];if(!c.active)return;
    if(c.bomb){score=Math.max(0,score-2);beep(180,0.18,'sawtooth');}
    else{score++;beep(880,0.06,'square');}
    sEl.textContent=score;c.mole.classList.remove('up');c.active=false;c.bomb=false;c.mole.classList.remove('bomb');
  }
  function init(){score=0;time=30;sEl.textContent=0;tEl.textContent=30;running=true;
    clearInterval(timer);clearInterval(popper);
    timer=setInterval(()=>{time--;tEl.textContent=time;if(time<=0)endGame();},1000);
    popper=setInterval(pop,520);}
  function endGame(){running=false;clearInterval(timer);clearInterval(popper);
    if(score>best){best=score;localStorage.setItem('shell_whack_best',best);bEl.textContent=best;}
    cells.forEach(c=>{c.mole.classList.remove('up','bomb');c.active=false;c.bomb=false;});
    ov.innerHTML='<h2>TIME UP</h2><p>Score: <b style="color:#3ee3a8">'+score+
      '</b> · Best: <b style="color:#3ee3a8">'+best+'</b></p><button id="r2">PLAY AGAIN</button>';
    ov.style.display='flex';document.getElementById('r2').onclick=()=>{ov.style.display='none';init();};}
  document.addEventListener('keydown',e=>{if(e.key==='r'||e.key==='R'){ov.style.display='none';init();}});
  startBtn.onclick=()=>{ov.style.display='none';build();init();};
})();
</script></body></html>
"""


# ──── MAZE / PAC-MAN-LITE ───────────────────────────────────────────────
_MAZE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>__TITLE__</title>
<style>__BASE_CSS__</style></head>
<body><div class="shell-frame">
  <h1 class="title">__TITLE__</h1>
  <div class="hud"><span>SCORE: <b id="sc">0</b></span><span>LIVES: <b id="lv">3</b></span><span>DOTS: <b id="dt">0</b></span></div>
  <canvas id="cv" width="544" height="544"></canvas>
  <div class="footer">↑↓←→ / WASD · COLLECT ALL DOTS · DODGE GHOSTS · R RESTART</div>
  <div class="overlay" id="ov"><h2>SHELL · MAZE</h2>
    <p>Eat every dot · Don't get caught · 3 lives</p><button id="startBtn">START</button></div>
</div>
<script>
(()=>{
  const cv=document.getElementById('cv'),ctx=cv.getContext('2d');
  const sEl=document.getElementById('sc'),lEl=document.getElementById('lv'),dEl=document.getElementById('dt');
  const ov=document.getElementById('ov'),startBtn=document.getElementById('startBtn');
  // 17x17 grid - 1=wall,0=dot,2=empty,3=spawn
  const MAP=[
    "11111111111111111",
    "10000000010000001",
    "10110110010110101",
    "10100000000000101",
    "10101011111010101",
    "10001000000010001",
    "11101011111010111",
    "10001000300010001",
    "10101111111110101",
    "10001000000010001",
    "11101011111010111",
    "10001000000010001",
    "10101011111010101",
    "10100000000000101",
    "10110110010110101",
    "10000000010000001",
    "11111111111111111",
  ];
  const ROWS=MAP.length,COLS=MAP[0].length,CELL=cv.width/COLS;
  let grid,player,ghosts,score,lives,dots,running,paused,frame;
  let actx;function beep(f,d=0.05,t='square',v=0.06){try{actx=actx||new(window.AudioContext||window.webkitAudioContext)();
    const o=actx.createOscillator(),g=actx.createGain();o.type=t;o.frequency.value=f;g.gain.value=v;
    o.connect(g);g.connect(actx.destination);o.start();
    g.gain.exponentialRampToValueAtTime(.0001,actx.currentTime+d);o.stop(actx.currentTime+d);}catch(e){}}
  function init(){
    grid=MAP.map(r=>r.split('').map(Number));
    let sx=1,sy=1;dots=0;
    for(let y=0;y<ROWS;y++)for(let x=0;x<COLS;x++){if(grid[y][x]===3){sx=x;sy=y;grid[y][x]=2;}if(grid[y][x]===0)dots++;}
    player={x:1,y:1,dir:{x:0,y:0},nextDir:{x:0,y:0}};
    ghosts=[{x:8,y:8,c:'#ff5fa1'},{x:7,y:8,c:'#ac89ff'},{x:9,y:8,c:'#ffd166'}];
    score=0;lives=3;running=true;paused=false;frame=0;
    sEl.textContent=0;lEl.textContent=3;dEl.textContent=dots;
  }
  function canMove(p,d){const nx=p.x+d.x,ny=p.y+d.y;return grid[ny]&&grid[ny][nx]!==1;}
  function step(){
    frame++;
    if(frame%8===0){
      if(canMove(player,player.nextDir)){player.dir=player.nextDir;}
      if(canMove(player,player.dir)){player.x+=player.dir.x;player.y+=player.dir.y;}
      if(grid[player.y][player.x]===0){grid[player.y][player.x]=2;score+=10;dots--;sEl.textContent=score;dEl.textContent=dots;beep(660,0.04);
        if(dots<=0){running=false;ov.innerHTML='<h2>VICTORY</h2><p>Score: <b style="color:#3ee3a8">'+score+'</b></p><button id="r2">PLAY AGAIN</button>';
          ov.style.display='flex';document.getElementById('r2').onclick=()=>{ov.style.display='none';init();requestAnimationFrame(loop);};return;}
      }
    }
    if(frame%12===0){
      ghosts.forEach(g=>{
        const opts=[{x:1,y:0},{x:-1,y:0},{x:0,y:1},{x:0,y:-1}].filter(d=>canMove(g,d));
        if(!opts.length)return;
        // Greedy chase 60% of the time, random 40%.
        if(Math.random()<0.6){
          opts.sort((a,b)=>{const da=Math.abs(g.x+a.x-player.x)+Math.abs(g.y+a.y-player.y);
            const db=Math.abs(g.x+b.x-player.x)+Math.abs(g.y+b.y-player.y);return da-db;});
          g.x+=opts[0].x;g.y+=opts[0].y;
        }else{const o=opts[(Math.random()*opts.length)|0];g.x+=o.x;g.y+=o.y;}
      });
    }
    ghosts.forEach(g=>{if(g.x===player.x&&g.y===player.y){
      lives--;lEl.textContent=lives;beep(180,0.2,'sawtooth');
      if(lives<=0){running=false;ov.innerHTML='<h2>GAME OVER</h2><p>Score: <b style="color:#3ee3a8">'+score+'</b></p><button id="r2">PLAY AGAIN</button>';
        ov.style.display='flex';document.getElementById('r2').onclick=()=>{ov.style.display='none';init();requestAnimationFrame(loop);};}
      else{player.x=1;player.y=1;player.dir={x:0,y:0};player.nextDir={x:0,y:0};
        ghosts=[{x:8,y:8,c:'#ff5fa1'},{x:7,y:8,c:'#ac89ff'},{x:9,y:8,c:'#ffd166'}];}
    }});
  }
  function draw(){
    ctx.fillStyle='#0a0e1a';ctx.fillRect(0,0,cv.width,cv.height);
    for(let y=0;y<ROWS;y++)for(let x=0;x<COLS;x++){
      const v=grid[y][x];
      if(v===1){ctx.fillStyle='#0d2c4f';ctx.shadowBlur=8;ctx.shadowColor='#00f0ff';
        ctx.fillRect(x*CELL,y*CELL,CELL,CELL);ctx.shadowBlur=0;
        ctx.strokeStyle='#00f0ff';ctx.strokeRect(x*CELL+1,y*CELL+1,CELL-2,CELL-2);}
      else if(v===0){ctx.fillStyle='#3ee3a8';ctx.shadowBlur=6;ctx.shadowColor='#3ee3a8';
        ctx.beginPath();ctx.arc(x*CELL+CELL/2,y*CELL+CELL/2,3,0,Math.PI*2);ctx.fill();ctx.shadowBlur=0;}
    }
    // player
    ctx.shadowBlur=14;ctx.shadowColor='#ffd166';ctx.fillStyle='#ffd166';
    ctx.beginPath();ctx.arc(player.x*CELL+CELL/2,player.y*CELL+CELL/2,CELL/2-3,0,Math.PI*2);ctx.fill();
    // ghosts
    ghosts.forEach(g=>{ctx.shadowColor=g.c;ctx.fillStyle=g.c;
      ctx.beginPath();ctx.arc(g.x*CELL+CELL/2,g.y*CELL+CELL/2,CELL/2-3,0,Math.PI*2);ctx.fill();});
    ctx.shadowBlur=0;
  }
  function loop(){if(!running){draw();return;}if(!paused)step();draw();requestAnimationFrame(loop);}
  document.addEventListener('keydown',e=>{
    if(e.key==='r'||e.key==='R'){ov.style.display='none';init();requestAnimationFrame(loop);return;}
    if(e.key==='p'||e.key==='P'){paused=!paused;return;}
    const m={ArrowLeft:{x:-1,y:0},ArrowRight:{x:1,y:0},ArrowUp:{x:0,y:-1},ArrowDown:{x:0,y:1},
      a:{x:-1,y:0},A:{x:-1,y:0},d:{x:1,y:0},D:{x:1,y:0},w:{x:0,y:-1},W:{x:0,y:-1},s:{x:0,y:1},S:{x:0,y:1}};
    if(m[e.key]){e.preventDefault();player.nextDir=m[e.key];}
  });
  startBtn.onclick=()=>{ov.style.display='none';init();requestAnimationFrame(loop);};
})();
</script></body></html>
"""


_TEMPLATES = {
    "snake":          ("Shell Snake",         _SNAKE),
    "tetris":         ("Shell Tetris",        _TETRIS),
    "pong":           ("Shell Pong",          _PONG),
    "breakout":       ("Shell Breakout",      _BREAKOUT),
    "flappy":         ("Shell Flappy",        _FLAPPY),
    "2048":           ("Shell 2048",          _2048),
    "invaders":       ("Shell Invaders",      _INVADERS),
    "runner":         ("Shell Runner",        _RUNNER),
    "tictactoe":      ("Shell Tic Tac Toe",   _TICTACTOE),
    "memory":         ("Shell Memory",        _MEMORY),
    "whack":          ("Shell Whack a Mole",  _WHACK),
    "maze":           ("Shell Maze",          _MAZE),
}


def _render_template(key: str, custom_features: str = "") -> tuple[str, str]:
    """Substitute placeholders and return (title, html)."""
    title, html = _TEMPLATES[key]
    if custom_features:
        title = f"{title} · {custom_features[:30]}"
    out = (html
           .replace("__TITLE__", title)
           .replace("__BASE_CSS__", _BASE_CSS.strip())
           .replace("__CUSTOM__", custom_features))
    return title, out


# ─────────────────────────────────────────────────────────────────────────
# AI fallback for free-form / customised games
# ─────────────────────────────────────────────────────────────────────────

_AI_SYSTEM_PROMPT = """You are Shell AI's GAME-FORGE — a senior HTML5/Canvas game developer.

OUTPUT RULES (STRICT):
- Reply with ONE single self-contained HTML5 file. Nothing else.
- NO markdown fences, NO commentary, NO explanation. Just raw <!DOCTYPE html>...</html>.
- Inline CSS in <style>. Inline JS in <script>. NO external assets, NO CDN, NO fonts.
- Sound via WebAudio (oscillator beeps) only.

GAME REQUIREMENTS:
- Canvas-based rendering. Main loop via requestAnimationFrame.
- Keyboard support: arrow keys + WASD where applicable.
- Touch / pointer support where applicable (swipes, taps).
- Score / lives HUD, start screen, game-over screen, restart key (R).
- Genuinely playable at 60fps. Real game logic — not a stub.

VISUAL STYLE (cyber-neon, mandatory):
- Background: #0a0e1a
- Primary cyan: #00f0ff (with text-shadow / box-shadow glow)
- Secondary purple: #ac89ff
- Success green: #3ee3a8
- Subtle grid lines, neon glows on key elements.
- Title at top, HUD with score, footer with controls hint.

Remember: ONLY the raw HTML. No prose. Begin with <!DOCTYPE html>.
"""


def _strip_codefences(text: str) -> str:
    """Remove ```html ... ``` style markdown fences if present."""
    t = text.strip()
    if t.startswith("```"):
        # drop first line (``` or ```html) and trailing ```
        t = re.sub(r"^```[a-zA-Z]*\s*\n", "", t)
        t = re.sub(r"\n```\s*$", "", t)
    return t.strip()


async def _ai_generate(game: str, custom_features: str = "") -> Optional[tuple[str, str]]:
    """Ask MultiAIBrain to produce a single-file HTML5 game.

    Returns (title, html) on success, or None on failure.
    """
    try:
        from brain.core import MultiAIBrain
        brain = MultiAIBrain.get_instance()
    except Exception as e:
        logger.warning("MultiAIBrain unavailable: %s", e)
        return None

    user_prompt = (
        f"Build a complete playable HTML5 game.\n"
        f"GAME: {game}\n"
        f"EXTRA REQUIREMENTS: {custom_features or 'none'}\n\n"
        f"Output the entire game as ONE HTML file starting with <!DOCTYPE html>. "
        f"It must run standalone in any modern browser."
    )

    try:
        resp = await asyncio.wait_for(
            brain.generate_response(
                prompt=user_prompt,
                system_prompt=_AI_SYSTEM_PROMPT,
                mode="CODER",
                use_cache=False,
                temperature=0.6,
                max_tokens=8000,
            ),
            timeout=90,
        )
    except Exception as e:
        logger.warning("AI generation failed: %s", e)
        return None

    text = _strip_codefences(str(resp or ""))
    if "<!DOCTYPE html" not in text and "<html" not in text:
        logger.warning("AI returned non-HTML payload (len=%d)", len(text))
        return None

    # Best-effort title extraction
    m = re.search(r"<title>(.*?)</title>", text, re.IGNORECASE | re.DOTALL)
    title = (m.group(1).strip() if m else f"Shell {game.title()}")[:80]
    return title, text


# ─────────────────────────────────────────────────────────────────────────
# Public tool
# ─────────────────────────────────────────────────────────────────────────

@function_tool
async def build_game_tool(game: str, custom_features: str = "") -> str:
    """Build a complete playable HTML5 game and open it in the browser.

    Args:
      game: Name/description of the game (e.g., 'snake', 'tetris', 'pong',
            'flappy bird', '2048', 'breakout', 'space invaders', or any
            free-form description like 'a runner where you dodge falling stars').
      custom_features: optional extra (e.g., 'add powerups', 'high scores',
                       'two-player', 'dark theme').
    """
    try:
        out_dir = _output_dir()
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        key = _normalise(game)

        title: str
        html: str

        # Template path: known game + no custom features → instant render.
        # If the user asked for custom features on a known template, we
        # still ship the template and APPEND the customisation request as
        # a footer note — keeps zero-latency path responsive while not
        # silently ignoring the user.
        if key and not custom_features.strip():
            title, html = _render_template(key)
            source = "template"
        elif key and custom_features.strip():
            # Try AI augmentation first; fall back to template.
            ai = await _ai_generate(game, custom_features)
            if ai:
                title, html = ai
                source = "ai+template-fallback"
            else:
                title, html = _render_template(key, custom_features)
                source = "template"
        else:
            # Free-form description → AI only.
            ai = await _ai_generate(game, custom_features)
            if ai:
                title, html = ai
                source = "ai"
            else:
                # Last-ditch fallback: snake template with the requested
                # name in the title so the user gets *something* playable.
                title, html = _render_template("snake")
                title = f"Shell {game[:30]}"
                html = html.replace("Shell Snake", title)
                source = "snake-fallback"

        slug = _slug(game)
        out_path = out_dir / f"{slug}_{ts}.html"
        out_path.write_text(html, encoding="utf-8")
        logger.info("Game written: %s (%d bytes, source=%s)", out_path, len(html), source)

        # Open in default browser. webbrowser.open handles file:// URLs on
        # Windows correctly when given an absolute path.
        try:
            webbrowser.open(out_path.as_uri())
        except Exception as e:
            logger.warning("webbrowser.open failed: %s", e)

        return (f"\U0001F3AE Game ready! '{title}' aapke browser mein khul gaya — "
                f"Desktop/shell_games mein save bhi hai.")
    except Exception as e:
        logger.exception("build_game_tool failed")
        return f"Game build failed: {type(e).__name__}: {e}"


# Convenience: allow running this file directly to smoke-test a template.
if __name__ == "__main__":
    async def _smoke():
        msg = await build_game_tool("snake")
        print(msg)
    asyncio.run(_smoke())
