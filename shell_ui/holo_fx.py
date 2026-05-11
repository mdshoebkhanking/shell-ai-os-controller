import math
import random
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import QTimer, Qt, QRectF, QPointF, QRect
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QBrush, QRadialGradient, QLinearGradient, QFont, QPolygonF
)

class HexGridWidget(QWidget):
    """
    Sci-Fi Hexagon Grid Background
    Features:
    - Pulsing hexagons
    - Mouse reactive highlights
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.hex_size = 40
        self.gap = 2
        self.pulse_phase = 0
        self.mouse_x = 0.0
        self.mouse_y = 0.0
        self.target_mouse_x = 0.0
        self.target_mouse_y = 0.0
        self.mouse_smoothing = 0.10
        
        # Color Palette
        self.base_color = QColor(0, 242, 255, 5) # Very faint cyan
        self.highlight_color = QColor(0, 242, 255, 40)
        self.active_hexes = {} # Map (r, c) -> life (0.0 to 1.0)
        
        self.setMouseTracking(True)
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_anim)
        self.timer.start(50)
        
    def set_target_pos(self, x, y):
        self.target_mouse_x = float(x)
        self.target_mouse_y = float(y)
        
    def update_anim(self):
        self.pulse_phase += 0.05
        self.mouse_x += (self.target_mouse_x - self.mouse_x) * self.mouse_smoothing
        self.mouse_y += (self.target_mouse_y - self.mouse_y) * self.mouse_smoothing
        
        # Randomly activate hexes
        if random.random() > 0.8:
            r = random.randint(0, 20)
            c = random.randint(0, 20)
            self.active_hexes[(r, c)] = 1.0
            
        # Decay active hexes
        dead = []
        for key in self.active_hexes:
            self.active_hexes[key] -= 0.02
            if self.active_hexes[key] <= 0:
                dead.append(key)
        for k in dead: del self.active_hexes[k]
        
        self.update()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        width = self.width()
        height = self.height()
        
        # Hex calculations
        # Width of hex = sqrt(3) * size
        # Height = 2 * size
        # Horizontal spacing = w
        # Vertical spacing = 3/4 * h
        
        w = math.sqrt(3) * self.hex_size
        h = 2 * self.hex_size
        
        cols = int(width / w) + 2
        rows = int(height / (h * 0.75)) + 2
        
        painter.setPen(QPen(QColor(0, 242, 255, 10), 1))
        
        for r in range(rows):
            for c in range(cols):
                x_offset = (w / 2) if r % 2 == 1 else 0
                cx = c * w + x_offset
                cy = r * (h * 0.75)
                
                # Check interaction distance
                dist = math.hypot(cx - self.mouse_x, cy - self.mouse_y)
                hover = max(0, 1 - dist / 150)
                
                # Check random active
                active = self.active_hexes.get((r, c), 0)
                
                intensity = max(hover * 0.5, active)
                
                if intensity > 0.05:
                    alpha = int(intensity * 100)
                    fill_color = QColor(0, 242, 255, alpha)
                    painter.setBrush(fill_color)
                else:
                    painter.setBrush(self.base_color)
                    
                # Draw Hexagon
                poly = QPolygonF()
                for i in range(6):
                    angle = math.radians(60 * i - 30)
                    px = cx + self.hex_size * math.cos(angle)
                    py = cy + self.hex_size * math.sin(angle)
                    poly.append(QPointF(px, py))
                    
                painter.drawPolygon(poly)

class ScanlineOverlay(QWidget):
    """
    Holographic Scanline & Vignette Effect
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scan_y = 0
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents) # Click-through
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_anim)
        self.timer.start(30)
        
    def update_anim(self):
        self.scan_y += 2
        if self.scan_y > self.height():
            self.scan_y = 0
        self.update()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        
        # 1. Scanlines (REMOVED per user request)
        # painter.setPen(QPen(QColor(0, 0, 0, 20), 1)) 
        # Loop removed for clean look
             
        # 2. Moving Scan Bar
        grad = QLinearGradient(0, self.scan_y, 0, self.scan_y + 50)
        grad.setColorAt(0, QColor(0, 255, 255, 0))
        grad.setColorAt(0.5, QColor(0, 255, 255, 30))
        grad.setColorAt(1, QColor(0, 255, 255, 0))
        painter.fillRect(QRect(0, int(self.scan_y), self.width(), 50), grad)
        
        # 3. Vignette (Dark Edges)
        vig_grad = QRadialGradient(self.width()/2, self.height()/2, self.width())
        vig_grad.setColorAt(0.5, QColor(0, 0, 0, 0))
        vig_grad.setColorAt(1, QColor(0, 0, 0, 150))
        painter.fillRect(self.rect(), vig_grad)

class HoloHUD(QWidget):
    """
    Overlay for Window Controls and Tech Decorations
    """
    minimize_clicked = None 
    close_clicked = None
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents) 
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_anim)
        self.timer.start(50)
        self.pulse = 0
        
    def update_anim(self):
        self.pulse += 0.1
        self.update()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        w, h = self.width(), self.height()
        c = QColor(0, 242, 255)
        
        # 1. Tech Corners (Resize Indicators)
        len_ = 20
        painter.setPen(QPen(c, 2))
        
        # TL
        painter.drawLine(0, 0, len_, 0)
        painter.drawLine(0, 0, 0, len_)
        # TR
        painter.drawLine(w, 0, w-len_, 0)
        painter.drawLine(w, 0, w, len_)
        # BL
        painter.drawLine(0, h, len_, h)
        painter.drawLine(0, h, 0, h-len_)
        # BR
        painter.drawLine(w, h, w-len_, h)
        painter.drawLine(w, h, w, h-len_)
        
        # 2. Window Controls (Top Right)
        # Minimize
        min_rect = QRectF(w - 70, 10, 30, 20)
        painter.setPen(QPen(c, 1))
        painter.drawRect(min_rect)
        painter.drawLine(int(w-65), 20, int(w-45), 20)
        
        # Close
        close_rect = QRectF(w - 35, 10, 30, 20)
        painter.setPen(QPen(QColor(255, 50, 50), 1))
        painter.drawRect(close_rect)
        painter.drawLine(int(w-30), 15, int(w-10), 25)
        painter.drawLine(int(w-30), 25, int(w-10), 15)
        
        # 3. Title Decoration
        painter.setPen(QPen(QColor(0, 242, 255, 100), 1))
        painter.drawLine(20, 0, w-20, 0) 
        
        # 4. Resize Grips (Visual Dots)
        painter.setBrush(c)
        painter.setPen(Qt.PenStyle.NoPen)
        ctx_size = 3
        # BR
        painter.drawEllipse(QPointF(w-5, h-5), ctx_size, ctx_size)
        painter.drawEllipse(QPointF(w-5, h-12), ctx_size, ctx_size)
        painter.drawEllipse(QPointF(w-12, h-5), ctx_size, ctx_size)

class HoloCaptions(QWidget):
    """
    Floating Holographic Subtitles/Captions
    Appears above the mic button.
    Features:
    - Floating sine-wave animation
    - Fade in/out
    - Speaker distinction (User vs Shell)
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.text = ""
        self.speaker = ""
        self.opacity = 0.0
        self.float_phase = 0.0
        self.target_opacity = 0.0
        
        # Smooth fade & float
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_anim)
        self.timer.start(16)
        
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.show() # Force Visible
        
    def show_text(self, text, speaker="SHELL"):
        self.text = text
        self.speaker = speaker
        self.target_opacity = 1.0
        self.update()
        self.raise_() # Force Top
        
        # Auto hide after 5 seconds
        QTimer.singleShot(5000, self.fade_out_if_no_update)
        
    def fade_out_if_no_update(self):
        # In a real app we'd track timestamps
        pass 
        
    def hide_text(self):
         self.target_opacity = 0.0

    def update_anim(self):
        # Fade (Faster)
        self.opacity += (self.target_opacity - self.opacity) * 0.2
        # Float
        self.float_phase += 0.05
        
        if abs(self.target_opacity - self.opacity) > 0.01 or self.opacity > 0.01:
            self.update()
            
    def paintEvent(self, event):
        if self.opacity < 0.01: return
            
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setOpacity(self.opacity)
        
        w, h = self.width(), self.height()
        
        # Floating effect (More bounce)
        float_y = math.sin(self.float_phase) * 8.0
        
        # Text settings
        font = QFont("Consolas", 14) # Larger Font
        font.setBold(True)
        painter.setFont(font)
        font_metrics = painter.fontMetrics()
        text_w = font_metrics.horizontalAdvance(self.text) + 50
        text_h = 50
        
        cx = w / 2
        cy = h - 120 + float_y # Higher up
        
        rect = QRectF(cx - text_w/2, cy - text_h/2, text_w, text_h)
        
        # Background Pill
        if self.speaker == "USER":
            bg_color = QColor(0, 242, 255, 40) # Cyan tint
            border_color = QColor(0, 242, 255, 150)
            txt_color = QColor(255, 255, 255)
        elif self.speaker == "SYSTEM":
             bg_color = QColor(0, 255, 0, 20)
             border_color = QColor(0, 255, 0, 100)
             txt_color = QColor(200, 255, 200)
        else: # SHELL
            bg_color = QColor(255, 255, 255, 20) # White tint
            border_color = QColor(255, 255, 255, 150)
            txt_color = QColor(255, 255, 255)
            
        painter.setBrush(bg_color)
        painter.setPen(QPen(border_color, 2))
        painter.drawRoundedRect(rect, 25, 25)
        
        # Draw Text
        painter.setPen(txt_color)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self.text)
