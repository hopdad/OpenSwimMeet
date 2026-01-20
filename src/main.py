import sys
from PyQt6.QtWidgets import QApplication
from src.app import MainApp

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainApp()
    window.show()
    sys.exit(app.exec())
