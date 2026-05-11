"""
Social Media Control Panel for Shell UI
Animated buttons for WhatsApp, Telegram, Instagram
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QDialog, QLineEdit, QDialogButtonBox, QFrame
)
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, pyqtProperty
from PyQt6.QtGui import QColor, QPainter, QBrush, QPen, QLinearGradient, QFont

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from shell_social_connector import social_connector

class AnimatedSocialButton(QPushButton):
    """Animated button with glow effect"""
    
    def __init__(self, platform: str, icon: str, color: QColor, parent=None):
        super().__init__(parent)
        self.platform = platform
        self.icon = icon
        self.base_color = color
        self.glow_intensity = 0.0
        self.is_connected = False
        
        self.setFixedSize(60, 60)
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: rgba({color.red()}, {color.green()}, {color.blue()}, 0.2);
                border: 2px solid rgba({color.red()}, {color.green()}, {color.blue()}, 0.5);
                border-radius: 30px;
                color: white;
                font-size: 24px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: rgba({color.red()}, {color.green()}, {color.blue()}, 0.4);
                border: 2px solid rgba({color.red()}, {color.green()}, {color.blue()}, 0.8);
            }}
        """)
        self.setText(icon)
        
        # Glow animation
        self.glow_timer = QTimer()
        self.glow_timer.timeout.connect(self._update_glow)
        self.glow_timer.start(50)
    
    def _update_glow(self):
        """Animate glow effect"""
        if self.is_connected:
            self.glow_intensity = (self.glow_intensity + 0.05) % 1.0
            self.update()
    
    def set_connected(self, connected: bool):
        """Update connection status"""
        self.is_connected = connected
        if connected:
            self.setStyleSheet(self.styleSheet() + f"""
                QPushButton {{
                    border: 3px solid {self.base_color.name()};
                }}
            """)
    
    def paintEvent(self, event):
        super().paintEvent(event)
        if self.is_connected and self.glow_intensity > 0:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            
            # Draw glow
            glow_color = QColor(self.base_color)
            glow_color.setAlphaF(self.glow_intensity * 0.5)
            painter.setPen(QPen(glow_color, 4))
            painter.drawEllipse(self.rect().adjusted(2, 2, -2, -2))


class ConnectionDialog(QDialog):
    """Dialog for connecting to social media"""
    
    def __init__(self, platform: str, parent=None):
        super().__init__(parent)
        self.platform = platform
        self.setWindowTitle(f"Connect {platform.title()}")
        self.setModal(True)
        
        # WhatsApp needs larger dialog for QR code
        if platform == "whatsapp":
            self.setFixedSize(500, 550)
        else:
            self.setFixedSize(400, 250)
        
        # Styling
        self.setStyleSheet("""
            QDialog {
                background-color: #0a0a0a;
                border: 2px solid #00f2ff;
                border-radius: 10px;
            }
            QLabel {
                color: #00f2ff;
                font-size: 14px;
            }
            QLineEdit {
                background-color: rgba(255, 255, 255, 0.1);
                border: 1px solid #00f2ff;
                border-radius: 5px;
                padding: 8px;
                color: white;
                font-size: 13px;
            }
            QPushButton {
                background-color: #00f2ff;
                color: black;
                border: none;
                border-radius: 5px;
                padding: 10px 20px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #00d4dd;
            }
        """)
        
        layout = QVBoxLayout()
        
        # Title
        title = QLabel(f"🔗 Connect to {platform.title()}")
        title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # Platform-specific content
        if platform == "whatsapp":
            # QR Code display
            self.qr_label = QLabel("📱 Scan QR Code with WhatsApp")
            self.qr_label.setFont(QFont("Arial", 12))
            self.qr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(self.qr_label)
            
            # QR Code image placeholder
            self.qr_image = QLabel()
            self.qr_image.setFixedSize(350, 350)
            self.qr_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.qr_image.setStyleSheet("background-color: white; border: 2px solid #00f2ff; border-radius: 10px;")
            self.qr_image.setText("Generating QR Code...")
            layout.addWidget(self.qr_image, alignment=Qt.AlignmentFlag.AlignCenter)
            
            # Instructions
            instructions = QLabel("1. Open WhatsApp on your phone\n2. Tap Menu (⋮) → Linked Devices\n3. Tap 'Link a Device'\n4. Scan this QR code")
            instructions.setStyleSheet("color: #888; font-size: 11px;")
            instructions.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(instructions)
            
            # Start QR generation
            self.start_whatsapp_connection()
            
        elif platform == "telegram":
            self.input = QLineEdit()
            self.input.setPlaceholderText("Enter bot token or phone number")
            layout.addWidget(QLabel("Credentials:"))
            layout.addWidget(self.input)
            
        elif platform == "instagram":
            self.input = QLineEdit()
            self.input.setPlaceholderText("Enter username")
            layout.addWidget(QLabel("Username:"))
            layout.addWidget(self.input)
        
        # Buttons (only for non-WhatsApp)
        if platform != "whatsapp":
            buttons = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
            )
            buttons.accepted.connect(self.accept)
            buttons.rejected.connect(self.reject)
            layout.addWidget(buttons)
        else:
            # Close button for WhatsApp
            close_btn = QPushButton("Close")
            close_btn.clicked.connect(self.reject)
            layout.addWidget(close_btn)
        
        self.setLayout(layout)
    
    def start_whatsapp_connection(self):
        """Start WhatsApp connection and display real QR"""
        from shell_whatsapp_web_real import whatsapp_web_real
        import threading
        
        def connect_thread():
            try:
                self.qr_label.setText("🌐 Opening WhatsApp Web...")
                success, result = whatsapp_web_real.start_session(headless=False)
                
                if success and result is None:
                    # Already logged in
                    self.qr_label.setText("✅ Already Connected!")
                    self.accept()
                elif success and result:
                    # Got QR code image
                    self.display_qr_image(result)
                    self.qr_label.setText("📱 Scan with WhatsApp App")
                    
                    # Wait for login in background
                    if whatsapp_web_real.wait_for_login():
                        self.qr_label.setText("✅ Connected!")
                        self.accept()
                else:
                    self.qr_label.setText(f"⚠️ {result}")
            except Exception as e:
                self.qr_label.setText(f"⚠️ Error: {str(e)}\n\nInstall: pip install selenium")
        
        # Run in background thread
        thread = threading.Thread(target=connect_thread, daemon=True)
        thread.start()
    
    def display_qr_image(self, pil_image):
        """Display PIL Image as QR code"""
        try:
            from PIL.ImageQt import ImageQt
            from PyQt6.QtGui import QPixmap
            
            # Resize to fit dialog
            pil_image = pil_image.resize((350, 350))
            
            # Convert to Qt format
            qt_img = ImageQt(pil_image)
            pixmap = QPixmap.fromImage(qt_img)
            
            self.qr_image.setPixmap(pixmap)
        except Exception as e:
            self.qr_image.setText(f"QR Display Error: {str(e)}")
    
    def display_qr_code(self, qr_text):
        """Display QR code in dialog"""
        try:
            import qrcode
            from PIL.ImageQt import ImageQt
            from PyQt6.QtGui import QPixmap
            
            # Generate QR code image
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=2,
            )
            qr.add_data(qr_text)
            qr.make(fit=True)
            
            img = qr.make_image(fill_color="black", back_color="white")
            
            # Resize to fit dialog
            img = img.resize((350, 350))
            
            # Convert to Qt format
            qt_img = ImageQt(img)
            pixmap = QPixmap.fromImage(qt_img)
            
            self.qr_image.setPixmap(pixmap)
            self.qr_label.setText("📱 Scan QR Code")
        except ImportError as e:
            self.qr_image.setText(f"⚠️ Missing library: {e}\n\nInstall: pip install qrcode pillow")
        except Exception as e:
            self.qr_image.setText(f"QR Code:\n{qr_text[:50]}...")
            print(f"QR display error: {e}")
    
    def get_credentials(self):
        """Get entered credentials"""
        if hasattr(self, 'input'):
            return self.input.text()
        return None


class SocialMediaPanel(QWidget):
    """Social Media Control Panel"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(80, 220)
        
        # Background
        self.setStyleSheet("""
            QWidget {
                background-color: rgba(10, 10, 10, 0.8);
                border: 1px solid rgba(0, 242, 255, 0.3);
                border-radius: 10px;
            }
        """)
        
        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Title
        title = QLabel("Social")
        title.setStyleSheet("color: #00f2ff; font-size: 10px; font-weight: bold;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # Buttons
        self.whatsapp_btn = AnimatedSocialButton("whatsapp", "💬", QColor(37, 211, 102))
        self.telegram_btn = AnimatedSocialButton("telegram", "✈️", QColor(0, 136, 204))
        self.instagram_btn = AnimatedSocialButton("instagram", "📷", QColor(225, 48, 108))
        
        self.whatsapp_btn.clicked.connect(lambda: self.connect_platform("whatsapp"))
        self.telegram_btn.clicked.connect(lambda: self.connect_platform("telegram"))
        self.instagram_btn.clicked.connect(lambda: self.connect_platform("instagram"))
        
        layout.addWidget(self.whatsapp_btn)
        layout.addWidget(self.telegram_btn)
        layout.addWidget(self.instagram_btn)
        
        self.setLayout(layout)
        
        # Update status
        self.update_status()
    
    def update_status(self):
        """Update button states based on connection status"""
        for platform, btn in [
            ("whatsapp", self.whatsapp_btn),
            ("telegram", self.telegram_btn),
            ("instagram", self.instagram_btn)
        ]:
            status = social_connector.get_status(platform)
            btn.set_connected(status["connected"])
    
    def connect_platform(self, platform: str):
        """Show connection dialog"""
        # Check if already connected
        if social_connector.get_status(platform)["connected"]:
            # Disconnect
            social_connector.disconnect(platform)
            self.update_status()
            return
        
        # Show dialog
        dialog = ConnectionDialog(platform, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            credentials = dialog.get_credentials()
            
            # Connect
            if platform == "whatsapp":
                success, msg = social_connector.connect_whatsapp(credentials)
            elif platform == "telegram":
                success, msg = social_connector.connect_telegram(credentials)
            elif platform == "instagram":
                success, msg = social_connector.connect_instagram(credentials)
            
            self.update_status()
            print(f"{'✅' if success else '❌'} {msg}")
