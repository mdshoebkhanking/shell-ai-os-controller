import sys
from PyQt6.QtWidgets import QApplication, QLabel, QMainWindow

app = QApplication(sys.argv)
window = QMainWindow()
window.setWindowTitle("Test")
window.setGeometry(100, 100, 400, 300)
label = QLabel("Qt Works!", window)
label.move(150, 130)
window.show()
print("Window created successfully!")
sys.exit(app.exec())
