from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel

class SettingsDialog(QDialog):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
    def result_settings(self):
        return {}
