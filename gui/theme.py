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


# Brand-approximate pill colors, one per health plan (see HEALTH_PLANS).
# Solid background with near-white text; theme-independent by design.
PLAN_COLORS = {
    "Aetna": "#7d3f98",
    "Anthem": "#1a9dd9",
    "BCBS": "#0033a0",
    "HF": "#e07b1a",
    "VCM": "#5c9e31",
    "AE": "#2bb3a3",
    "ES": "#c0392b",
    "HC": "#b8860b",
    "HOF": "#c0507e",
}


def build_qss(t: dict) -> str:
    plan_rules = "\n".join(
        f'QLabel#plan_badge[plan="{code}"] {{ background-color: {color}; '
        f'color: #f4f6fd; border: 1px solid {color}; }}'
        for code, color in PLAN_COLORS.items()
    )
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
QPushButton#btn_discard {{
    background-color: {t['error']};
    color: #ffffff;
    border: none;
    font-weight: 600;
}}
QPushButton#btn_discard:hover {{
    background-color: {t['error_text']};
}}
/* Grayed out until there are unsaved edits. */
QPushButton#btn_save:disabled, QPushButton#btn_discard:disabled {{
    background-color: {t['surface']};
    color: {t['text4']};
    border: 1px solid {t['border_mid']};
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
/* QDateEdit calendar popup: the global input padding above squeezes the
   navbar's year editor so the digits clip. Give it room and lighter padding
   (no margin — a margin on a styled spinbox breaks the step-button geometry). */
QCalendarWidget QSpinBox {{
    min-width: 72px;
    padding: 2px 6px;
    font-size: 12px;
}}
/* Hide the year spinner's step buttons: once the spinbox is styled their hit
   area can overlap the field and increment the year on a plain click. The year
   stays editable by typing. */
QCalendarWidget QSpinBox::up-button,
QCalendarWidget QSpinBox::down-button {{
    width: 0px;
    border: none;
}}
QCalendarWidget QToolButton {{
    color: {t['text']};
    background-color: transparent;
    padding: 4px 10px;
}}
QCalendarWidget QToolButton:hover {{
    background-color: {t['raised']};
    border-radius: 5px;
}}
/* Inline view/edit fields on the member Info tab: flat selectable text by
   default, a box only while being edited, a left accent when changed-unsaved. */
QLineEdit#info_field, QLineEdit#info_field:read-only {{
    background: transparent;
    border: none;
    border-radius: 0;
    color: {t['text']};
    padding: 3px 2px;
}}
QLineEdit#info_field[changed="true"],
QLineEdit#info_field[changed="true"]:read-only {{
    border-left: 2px solid {t['accent']};
    padding-left: 7px;
}}
/* Empty editable field: an obvious dashed box so staff know it's there to fill. */
QLineEdit#info_field[empty="true"],
QLineEdit#info_field[empty="true"]:read-only {{
    background-color: {t['raised']};
    border: 1px dashed {t['border']};
    border-radius: 4px;
    padding: 3px 6px;
}}
QLineEdit#info_field[editing="true"] {{
    background-color: {t['raised']};
    border: 1px solid {t['accent']};
    border-radius: 4px;
    padding: 3px 6px;
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
QToolBar#main_toolbar {{
    background-color: {t['surface']};
    border-bottom: 1px solid {t['border_mid']};
    padding: 5px 10px;
    spacing: 6px;
}}
QPushButton#btn_settings {{
    background-color: {t['accent_bg']};
    color: {t['accent_text']};
    border: 1px solid {t['accent']};
    border-radius: 7px;
    padding: 7px 16px;
    font-size: 12px;
    font-weight: 600;
}}
QPushButton#btn_settings:hover {{
    background-color: {t['accent']};
    color: #ffffff;
}}
QLabel#db_indicator {{
    background-color: transparent;
    font-size: 12px;
    font-weight: 600;
    padding: 4px 6px;
    color: {t['text2']};
}}
QLabel#db_indicator[connected="true"] {{
    color: {t['accent_text']};
}}
QLabel#db_indicator[connected="false"] {{
    color: {t['warning']};
}}
QPushButton#btn_terminate {{
    background-color: {t['error']};
    color: #ffffff;
    border: none;
    font-weight: 600;
    padding: 4px 12px;
    border-radius: 5px;
}}
QPushButton#btn_terminate:hover {{
    background-color: {t['error_text']};
}}
QPushButton#btn_edit {{
    background-color: {t['accent_bg']};
    color: {t['accent_text']};
    border: 1px solid {t['accent']};
    font-weight: 600;
    padding: 4px 12px;
    border-radius: 5px;
}}
QPushButton#btn_edit:hover {{
    background-color: {t['accent']};
    color: #ffffff;
}}
QLabel {{
    background-color: transparent;
    color: {t['text']};
}}
QLabel#section_header {{
    color: {t['accent_text']};
    font-size: 10px;
    font-weight: 700;
    border-bottom: 1px solid {t['border_mid']};
    padding: 6px 0 2px 0;
}}
QLabel#field_label {{
    color: {t['text3']};
    font-size: 11px;
    padding-right: 2px;
}}
QLabel#notes_label {{
    color: {t['accent_text']};
    font-size: 11px;
    font-weight: 700;
}}
QTextEdit#notes_edit {{
    background-color: {t['accent_bg']};
    border: 1px solid {t['border']};
    border-radius: 6px;
}}
QTextEdit#notes_edit:focus {{
    border-color: {t['accent']};
}}
QLabel#day_chip_on {{
    background-color: {t['accent']};
    color: #f4f6fd;
    border: 1px solid {t['accent']};
    border-radius: 9px;
    padding: 3px 0;
    font-size: 10px;
    font-weight: 700;
}}
QLabel#day_chip_off {{
    background-color: {t['surface']};
    color: {t['text2']};
    border: 1px solid {t['border']};
    border-radius: 9px;
    padding: 3px 0;
    font-size: 10px;
    font-weight: 600;
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
QLabel#terminated_badge {{
    background-color: {t['error']};
    color: #f4f6fd;
    border: none;
    border-radius: 10px;
    padding: 3px 10px;
    font-size: 11px;
    font-weight: 700;
}}
QLabel#expired_chip {{
    background-color: {t['error_bg']};
    color: {t['error_text']};
    border: 1px solid {t['error']};
    border-radius: 8px;
    padding: 1px 7px;
    font-size: 9px;
    font-weight: 700;
}}
QLabel#active_chip {{
    background-color: {t['success_bg']};
    color: {t['success']};
    border: 1px solid {t['success']};
    border-radius: 8px;
    padding: 1px 7px;
    font-size: 9px;
    font-weight: 700;
}}
QLabel#upcoming_chip {{
    background-color: {t['warning_bg']};
    color: {t['warning']};
    border: 1px solid {t['warning']};
    border-radius: 8px;
    padding: 1px 7px;
    font-size: 9px;
    font-weight: 700;
}}
/* Current Schedule strip cells on the Availability tab. */
QWidget#avail_day {{
    background-color: {t['raised']};
    border: 1px solid {t['border']};
    border-radius: 7px;
}}
QWidget#avail_day_empty {{
    background-color: {t['surface']};
    border: 1px dashed {t['border']};
    border-radius: 7px;
}}
QLabel#avail_day_name {{
    color: {t['text3']};
    font-size: 10px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
}}
QLabel#avail_day_time {{
    color: {t['text']};
    font-size: 12px;
    font-weight: 600;
}}
QLabel#avail_day_dash {{
    color: {t['text3']};
    font-size: 12px;
    font-weight: 600;
}}
QLabel#strip_caption {{
    color: {t['text3']};
    font-size: 10px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
}}
QLabel#plan_badge {{
    background-color: {t['accent_bg']};
    color: {t['accent_text']};
    border: 1px solid {t['accent']};
    border-radius: 10px;
    padding: 3px 10px;
    font-size: 11px;
    font-weight: 700;
}}
{plan_rules}
QLabel#wizard_warning {{
    background-color: {t['warning_bg']};
    color: {t['warning']};
    border: 1px solid {t['warning']};
    border-radius: 7px;
    padding: 10px;
    font-size: 11px;
}}
QWidget#wizard_panel {{
    background-color: {t['surface']};
    border: 1px solid {t['border_mid']};
    border-radius: 10px;
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
