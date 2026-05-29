"""Dark/light theme tokens and QSS generator.

Colors are pre-converted from OKLCH to sRGB hex. Call apply_theme(app, "dark")
or apply_theme(app, "light") to swap at runtime.
"""

DARK = {
    "bg":           "#141519",
    "surface":      "#181b20",
    "raised":       "#1e2128",
    "border":       "#282c38",
    "border_mid":   "#232730",
    "text":         "#dde0f2",
    "text2":        "#757a98",
    "text3":        "#434760",
    "text4":        "#31354a",
    "accent":       "#5b7cf4",
    "accent_hover": "#6e8cf6",
    "accent_bg":    "#1c2040",
    "accent_text":  "#92b4ff",
    "success":      "#3d9e6e",
    "success_bg":   "#182e22",
    "warning":      "#c08a2a",
    "warning_bg":   "#281f0a",
    "error":        "#d05555",
    "error_bg":     "#2e1515",
    "error_text":   "#e08080",
}

LIGHT = {
    "bg":           "#f5f6fa",
    "surface":      "#eaebf0",
    "raised":       "#fdfefe",
    "border":       "#ced1e0",
    "border_mid":   "#dfe0e8",
    "text":         "#252838",
    "text2":        "#515670",
    "text3":        "#7e8090",
    "text4":        "#a8aab8",
    "accent":       "#3b5ce0",
    "accent_hover": "#2e4ec2",
    "accent_bg":    "#e5eafc",
    "accent_text":  "#2c47b8",
    "success":      "#1e7a4e",
    "success_bg":   "#e8f5ee",
    "warning":      "#876010",
    "warning_bg":   "#f5f0e0",
    "error":        "#b83a3a",
    "error_bg":     "#f5e8e8",
    "error_text":   "#902a2a",
}


def build_qss(t: dict) -> str:
    return f"""
QMainWindow, QDialog, QWidget {{
    background-color: {t['bg']};
    color: {t['text']};
    font-family: "Segoe UI", system-ui, sans-serif;
    font-size: 13px;
}}
QWidget#sidebar {{
    background-color: {t['surface']};
    border-right: 1px solid {t['border_mid']};
}}
QWidget#detail {{
    background-color: {t['bg']};
}}
QPushButton {{
    background-color: {t['raised']};
    color: {t['text2']};
    border: 1px solid {t['border']};
    border-radius: 7px;
    padding: 7px 16px;
    font-size: 12px;
    font-weight: 500;
}}
QPushButton:hover {{
    background-color: {t['border']};
    color: {t['text']};
}}
QPushButton:pressed {{
    background-color: {t['border_mid']};
}}
QPushButton:disabled {{
    color: {t['text4']};
    background-color: {t['surface']};
    border-color: {t['border_mid']};
}}
QPushButton#btn_primary {{
    background-color: {t['accent']};
    color: #ffffff;
    border: none;
    font-weight: 600;
}}
QPushButton#btn_primary:hover {{
    background-color: {t['accent_hover']};
}}
QPushButton#btn_add {{
    background-color: {t['accent']};
    color: #ffffff;
    border: none;
    font-weight: 600;
    border-radius: 7px;
    padding: 8px 12px;
    font-size: 12px;
}}
QPushButton#btn_add:hover {{
    background-color: {t['accent_hover']};
}}
QPushButton#btn_save {{
    background-color: {t['success']};
    color: #ffffff;
    border: none;
    font-weight: 600;
}}
QPushButton#btn_save:hover {{
    background-color: {t['success']};
    opacity: 0.9;
}}
QLineEdit, QComboBox, QDateEdit, QTimeEdit, QSpinBox {{
    background-color: {t['raised']};
    color: {t['text']};
    border: 1px solid {t['border']};
    border-radius: 5px;
    padding: 7px 10px;
    font-size: 12px;
    selection-background-color: {t['accent_bg']};
    selection-color: {t['text']};
}}
QLineEdit:focus, QComboBox:focus, QDateEdit:focus, QTimeEdit:focus {{
    border-color: {t['accent']};
}}
QLineEdit:read-only {{
    background-color: {t['surface']};
    color: {t['text3']};
    border-style: dashed;
}}
QComboBox::drop-down {{
    border: none;
    padding-right: 8px;
}}
QComboBox QAbstractItemView {{
    background-color: {t['raised']};
    color: {t['text']};
    border: 1px solid {t['border']};
    selection-background-color: {t['accent_bg']};
}}
QListWidget {{
    background-color: transparent;
    border: none;
    outline: none;
}}
QListWidget::item {{
    border-radius: 5px;
    padding: 7px 9px;
    color: {t['text2']};
}}
QListWidget::item:hover {{
    background-color: {t['raised']};
}}
QListWidget::item:selected {{
    background-color: {t['accent_bg']};
    color: {t['accent_text']};
}}
QTabWidget::pane {{
    border-top: 1px solid {t['border_mid']};
    background-color: {t['bg']};
}}
QTabBar::tab {{
    background-color: transparent;
    color: {t['text3']};
    padding: 6px 14px;
    border-bottom: 2px solid transparent;
    font-size: 11px;
    font-weight: 500;
}}
QTabBar::tab:selected {{
    color: {t['accent_text']};
    border-bottom-color: {t['accent']};
}}
QTabBar::tab:hover:!selected {{
    color: {t['text2']};
}}
QLabel {{
    background-color: transparent;
    color: {t['text']};
}}
QLabel#label_field {{
    color: {t['text3']};
    font-size: 10px;
    font-weight: 600;
}}
QLabel#warning_badge {{
    background-color: {t['error_bg']};
    color: {t['error_text']};
    border: 1px solid {t['error']};
    border-radius: 10px;
    padding: 3px 10px;
    font-size: 10px;
    font-weight: 500;
}}
QScrollBar:vertical {{
    background: {t['surface']};
    width: 6px;
    border: none;
}}
QScrollBar::handle:vertical {{
    background: {t['border']};
    border-radius: 3px;
    min-height: 20px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QTableWidget {{
    background-color: {t['bg']};
    color: {t['text']};
    border: 1px solid {t['border_mid']};
    border-radius: 7px;
    gridline-color: {t['border_mid']};
    font-size: 12px;
}}
QTableWidget::item {{
    padding: 6px 10px;
}}
QTableWidget::item:selected {{
    background-color: {t['accent_bg']};
    color: {t['text']};
}}
QHeaderView::section {{
    background-color: {t['surface']};
    color: {t['text3']};
    border: none;
    border-bottom: 1px solid {t['border_mid']};
    padding: 6px 10px;
    font-size: 10px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
}}
"""


def apply_theme(app, theme_name: str) -> None:
    """Apply 'dark' or 'light' QSS to the entire application."""
    tokens = DARK if theme_name == "dark" else LIGHT
    app.setStyleSheet(build_qss(tokens))
