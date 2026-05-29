import sys
import os
from PyQt6.QtWidgets import QApplication, QMessageBox
from gui.main_window import MainWindow
from gui.theme import apply_theme
from settings import load_settings

SETTINGS_PATH = os.path.join(os.path.dirname(__file__), "bsca_members_settings.json")


def main():
    app = QApplication(sys.argv)
    settings = load_settings(SETTINGS_PATH)
    apply_theme(app, settings.get("theme", "dark"))
    window = MainWindow(settings, SETTINGS_PATH)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
