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
    # Info tab per-field highlight tints (customizable layout).
    "hl_amber":     "#3a2f10",
    "hl_blue":      "#1c2745",
    "hl_green":     "#16301f",
    "hl_red":       "#391b1b",
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
    # Info tab per-field highlight tints (customizable layout).
    "hl_amber":     "#f7ecc8",
    "hl_blue":      "#dfe7fb",
    "hl_green":     "#ddf0e4",
    "hl_red":       "#f7dede",
}


# Brand-approximate pill colors, one per health plan (see HEALTH_PLANS).
# Solid background with near-white text; theme-independent by design.
# Health-plan badge colors, matched to the staff's physical color-dot legend
# (AE green, BCBS yellow, VCM orange, ES red, HOF blue, HF pink, HC purple).
# Aetna/Anthem are legacy (dropped from HEALTH_PLANS) and kept so any
# not-yet-migrated rows still render a badge. Text color is auto-picked per
# background (see _readable_text) so light colors like yellow/orange stay legible.
PLAN_COLORS = {
    "Aetna": "#7d3f98",
    "Anthem": "#1a9dd9",
    "AE": "#3f9e35",    # green
    "BCBS": "#f2ce1b",  # yellow
    "VCM": "#e6912f",   # orange
    "ES": "#d83a30",    # red
    "HOF": "#2f5fd0",   # blue
    "HF": "#d02f63",    # pink / magenta
    "HC": "#6a2fa0",    # purple
}


def _readable_text(hex_color: str) -> str:
    """Dark text on light badge colors, white on dark ones (perceptual
    luminance), so e.g. yellow/orange badges stay legible."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    luminance = 0.299 * r + 0.587 * g + 0.114 * b
    return "#1c1e26" if luminance > 150 else "#f4f6fd"


def build_qss(t: dict) -> str:
    plan_rules = "\n".join(
        f'QLabel#plan_badge[plan="{code}"] {{ background-color: {color}; '
        f'color: {_readable_text(color)}; border: 1px solid {color}; }}'
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
/* Grouped sections (Company Calendar). Qt's native group-box frame ignores the
   palette and draws light chrome on the dark theme, so give it the app's panel
   border and radius and sit the title on the border line. */
QGroupBox {{
    border: 1px solid {t['border_mid']};
    border-radius: 7px;
    margin-top: 10px;
    padding: 12px 10px 10px 10px;
    font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0 6px;
    color: {t['text']};
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
/* Invalid input / failed-constraint highlight (set via the `error` property). */
QLineEdit[error="true"], QComboBox[error="true"], QDateEdit[error="true"] {{
    border: 1px solid {t['error']};
}}
QLineEdit:read-only {{
    background-color: {t['surface']};
    color: {t['text3']};
    border-style: dashed;
}}
/* Date fields use the calendar popup, not up/down steppers. Once a QDateEdit is
   styled, Qt renders spin buttons on the right whose hit area increments the
   highlighted section on a click. Hide them and show only the calendar arrow. */
QDateEdit::up-button, QDateEdit::down-button {{
    width: 0px;
    border: none;
}}
QDateEdit::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: center right;
    width: 22px;
    border: none;
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
    font-size: 13px;
    font-weight: 600;          /* bolder values so they read clearly */
    padding: 3px 2px;
}}
/* Customizable layout styling for Info fields (dynamic properties set from
   the saved layout — see gui/info_layout.py). Placed before the state rules
   ([changed]/[empty]/[editing]/[error]) so those later, equal-specificity
   states keep winning their background/border while bold/large persist. */
QLineEdit#info_field[fbold="true"] {{ font-weight: 800; }}
QLineEdit#info_field[fsize="small"] {{ font-size: 11px; }}
QLineEdit#info_field[fsize="large"] {{ font-size: 16px; }}
QLineEdit#info_field[fsize="xlarge"] {{ font-size: 20px; }}
QLineEdit#info_field[hl="amber"], QLineEdit#info_field[hl="amber"]:read-only {{
    background-color: {t['hl_amber']}; border-radius: 4px; padding: 3px 6px;
}}
QLineEdit#info_field[hl="blue"], QLineEdit#info_field[hl="blue"]:read-only {{
    background-color: {t['hl_blue']}; border-radius: 4px; padding: 3px 6px;
}}
QLineEdit#info_field[hl="green"], QLineEdit#info_field[hl="green"]:read-only {{
    background-color: {t['hl_green']}; border-radius: 4px; padding: 3px 6px;
}}
QLineEdit#info_field[hl="red"], QLineEdit#info_field[hl="red"]:read-only {{
    background-color: {t['hl_red']}; border-radius: 4px; padding: 3px 6px;
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
/* Invalid value (failed validation) on an inline Info field. */
QLineEdit#info_field[error="true"] {{
    border: 1px solid {t['error']};
    border-radius: 4px;
    padding: 3px 6px;
}}
/* Customizable Info tab per-field styling, driven by dynamic properties set
   from the saved layout (see gui/info_layout.py). Generic fallback for any
   customizable line edit without the #info_field object name; currently
   redundant (the address inner edit uses #info_field too) but kept as a
   safety net. */
QLineEdit[fbold="true"] {{ font-weight: 800; }}
QLineEdit[fsize="small"] {{ font-size: 11px; }}
QLineEdit[fsize="large"] {{ font-size: 16px; }}
QLineEdit[fsize="xlarge"] {{ font-size: 20px; }}
QLineEdit[hl="amber"], QLineEdit[hl="amber"]:read-only {{
    background-color: {t['hl_amber']}; border-radius: 4px; padding: 3px 6px;
}}
QLineEdit[hl="blue"], QLineEdit[hl="blue"]:read-only {{
    background-color: {t['hl_blue']}; border-radius: 4px; padding: 3px 6px;
}}
QLineEdit[hl="green"], QLineEdit[hl="green"]:read-only {{
    background-color: {t['hl_green']}; border-radius: 4px; padding: 3px 6px;
}}
QLineEdit[hl="red"], QLineEdit[hl="red"]:read-only {{
    background-color: {t['hl_red']}; border-radius: 4px; padding: 3px 6px;
}}
QComboBox::drop-down {{
    border: none;
    width: 22px;
}}
/* A visible arrow so combo boxes read as pickers, not text fields. */
QComboBox::down-arrow {{
    image: none;
    width: 0;
    height: 0;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid {t['text2']};
    margin-right: 8px;
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
QPushButton#btn_export, QPushButton#btn_expiring_report,
QPushButton#btn_birthday_report, QPushButton#btn_absence_report,
QPushButton#btn_company_calendar, QPushButton#btn_bookmarks {{
    background-color: transparent;
    color: {t['text2']};
    border: 1px solid {t['border']};
    border-radius: 7px;
    padding: 7px 12px;
    font-size: 12px;
    font-weight: 600;
}}
QPushButton#btn_export:hover, QPushButton#btn_expiring_report:hover,
QPushButton#btn_birthday_report:hover, QPushButton#btn_absence_report:hover,
QPushButton#btn_company_calendar:hover, QPushButton#btn_bookmarks:hover {{
    background-color: {t['raised']};
    color: {t['text']};
}}
/* Member-header bookmark toggle: quiet outline until the member is
   bookmarked, then accent-tinted (the [marked] property drives the state). */
QPushButton#btn_bookmark {{
    background-color: transparent;
    color: {t['text2']};
    border: 1px solid {t['border']};
    border-radius: 6px;
    padding: 3px 10px;
    font-size: 12px;
    font-weight: 600;
}}
QPushButton#btn_bookmark:hover {{
    background-color: {t['accent_bg']};
    color: {t['accent_text']};
    border-color: {t['accent']};
}}
QPushButton#btn_bookmark[marked="true"] {{
    background-color: {t['accent_bg']};
    color: {t['accent_text']};
    border-color: {t['accent']};
}}
/* Toolbar notifications bell: quiet until something needs attention;
   red-tinted when any authorization has expired. */
QPushButton#btn_notifications {{
    background-color: transparent;
    color: {t['text2']};
    border: 1px solid {t['border']};
    border-radius: 7px;
    padding: 7px 12px;
    font-size: 12px;
    font-weight: 600;
}}
QPushButton#btn_notifications:hover {{
    background-color: {t['raised']};
    color: {t['text']};
}}
QPushButton#btn_notifications[alert="true"] {{
    color: {t['error_text']};
    border-color: {t['error']};
    background-color: {t['error_bg']};
}}
QFrame#notif_frame {{
    background-color: {t['raised']};
    border: 1px solid {t['border']};
    border-radius: 10px;
}}
QLabel#notif_title {{
    font-size: 13px;
    font-weight: 600;
    color: {t['text']};
}}
QPushButton#notif_tab {{
    background: transparent;
    border: none;
    border-bottom: 2px solid transparent;
    border-radius: 0;
    padding: 7px 12px;
    font-size: 12px;
    font-weight: 500;
    color: {t['text2']};
}}
QPushButton#notif_tab:hover {{
    color: {t['text']};
}}
QPushButton#notif_tab[active="true"] {{
    color: {t['accent_text']};
    border-bottom-color: {t['accent']};
    font-weight: 600;
}}
QFrame#notif_row {{
    background: transparent;
    border: none;
}}
QFrame#notif_row:hover {{
    background-color: {t['accent_bg']};
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
/* Destructive but calm: outline style until hovered, and never wider than
   its text (the cell wrapper keeps it from stretching across the table). */
QPushButton#btn_terminate {{
    background-color: {t['error_bg']};
    color: {t['error_text']};
    border: 1px solid {t['error']};
    font-weight: 600;
    padding: 3px 14px;
    border-radius: 5px;
}}
QPushButton#btn_terminate:hover {{
    background-color: {t['error']};
    color: #ffffff;
}}
/* Muted line shown inside empty tables / lists ("No … yet — click + Add"). */
QLabel#empty_state {{
    color: {t['text3']};
    font-size: 12px;
    font-style: italic;
    padding: 18px;
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
/* Compact icon-only delete (the ✕ on a scheduled change): muted by default,
   red on hover so it reads as a destructive action. */
QPushButton#btn_icon_delete {{
    background-color: transparent;
    color: {t['text3']};
    border: 1px solid {t['border']};
    font-weight: 700;
    padding: 4px 0;
    border-radius: 5px;
}}
QPushButton#btn_icon_delete:hover {{
    background-color: {t['error']};
    color: #ffffff;
    border-color: {t['error']};
}}
/* Compact icon-only edit (the ✎ on a scheduled change): accent on hover. */
QPushButton#btn_icon_edit {{
    background-color: {t['accent_bg']};
    color: {t['accent_text']};
    border: 1px solid {t['accent']};
    font-weight: 700;
    padding: 4px 0;
    border-radius: 5px;
}}
QPushButton#btn_icon_edit:hover {{
    background-color: {t['accent']};
    color: #ffffff;
}}
/* Row Add (green) / Delete (red) action buttons. Delete is grayed + disabled
   until a row is selected. */
QPushButton#btn_row_add {{
    background-color: {t['success_bg']};
    color: {t['success']};
    border: 1px solid {t['success']};
    font-weight: 600;
    padding: 5px 14px;
    border-radius: 5px;
}}
QPushButton#btn_row_add:hover {{
    background-color: {t['success']};
    color: #ffffff;
}}
QPushButton#btn_row_delete {{
    background-color: {t['error_bg']};
    color: {t['error']};
    border: 1px solid {t['error']};
    font-weight: 600;
    padding: 5px 14px;
    border-radius: 5px;
}}
QPushButton#btn_row_delete:hover {{
    background-color: {t['error']};
    color: #ffffff;
}}
QPushButton#btn_row_delete:disabled {{
    background-color: {t['surface']};
    color: {t['text4']};
    border: 1px solid {t['border_mid']};
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
/* Global label size from the customizable layout ("normal" = the 11px base
   above; the lsize property is stamped by _make_info_tab). */
QLabel#field_label[lsize="small"] {{ font-size: 9px; }}
QLabel#field_label[lsize="large"] {{ font-size: 13px; }}
/* Ctrl+K quick-search palette: a floating rounded card with a big search box. */
QWidget#quick_search {{
    background-color: {t['surface']};
    border: 1px solid {t['border_mid']};
    border-radius: 12px;
}}
QLineEdit#quick_search_input {{
    background-color: {t['raised']};
    border: 1px solid {t['border']};
    border-radius: 8px;
    font-size: 15px;
    padding: 10px 12px;
}}
QListWidget#quick_search_list {{
    background: transparent;
    border: none;
}}
QLabel#quick_search_hint {{
    color: {t['text3']};
    font-size: 10px;
}}
/* Schedule summary card on the Info tab: a contained, spaced-out row instead of
   stretched grid cells. */
QWidget#schedule_card {{
    background-color: {t['raised']};
    border: 1px solid {t['border']};
    border-radius: 10px;
}}
QLabel#schedule_value {{
    color: {t['text']};
    font-size: 13px;
    font-weight: 700;
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
QLabel#alt_id_label {{
    color: {t['text2']};
    font-size: 12px;
    font-weight: 600;
}}
QPushButton#alt_id_add {{
    background: transparent;
    border: none;
    color: {t['text2']};
    font-size: 12px;
    font-weight: 600;
    padding: 0px;
}}
QPushButton#alt_id_add:hover {{
    color: {t['accent']};
    text-decoration: underline;
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
/* Authorized days: a light-green tint (kept subtle so the time stays legible). */
QWidget#avail_day[authorized="true"] {{
    background-color: {t['success_bg']};
    border: 1px solid {t['success']};
}}
QWidget#avail_day_empty[authorized="true"] {{
    background-color: {t['success_bg']};
    border: 1px solid {t['success']};
}}
QLabel#avail_day_name {{
    color: {t['text3']};
    font-size: 10px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
}}
QLabel#avail_legend_swatch {{
    background-color: {t['success_bg']};
    border: 1px solid {t['success']};
    border-radius: 3px;
}}
QLabel#avail_legend {{
    color: {t['text3']};
    font-size: 10px;
    font-weight: 600;
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
/* Wrapper around a centered pill/button in a table cell. Transparent so the
   row's own background (e.g. the Availability tab's authorized-day tint) shows
   through instead of the fill it would otherwise inherit from QTableWidget. */
QWidget#pill_cell {{
    background: transparent;
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


# The active theme, kept current by apply_theme so widgets built later (event
# badges, count labels) can color themselves without threading the settings
# dict everywhere.
_current_name = "dark"


def current_theme_name() -> str:
    return _current_name


def current_tokens() -> dict:
    """The token dict of the theme applied last (defaults to dark)."""
    return DARK if _current_name == "dark" else LIGHT


# Event-type badge colors per theme (bg, fg). The dark values are the original
# palette; the light values keep the same hues on pale backgrounds.
EVENT_BADGE_COLORS = {
    "dark": {
        "NEW":    ("#182e22", "#3d9e6e"),
        "EDIT":   ("#281f0a", "#c08a2a"),
        "AUTH":   ("#1c2040", "#92b4ff"),
        "ABS":    ("#1e1530", "#b090e8"),
        "AVAIL":  ("#0e2028", "#5eead4"),
        "ENROLL": ("#1a2030", "#80b0e8"),
    },
    "light": {
        "NEW":    ("#e8f5ee", "#1e7a4e"),
        "EDIT":   ("#f5f0e0", "#876010"),
        "AUTH":   ("#e5eafc", "#2c47b8"),
        "ABS":    ("#efe8f8", "#6a3fa8"),
        "AVAIL":  ("#e0f4f2", "#0f766e"),
        "ENROLL": ("#e6eef8", "#2a5f9e"),
    },
}


def event_badge_colors(event_type: str) -> tuple[str, str]:
    """(background, foreground) for an event-type badge in the active theme."""
    palette = EVENT_BADGE_COLORS[_current_name]
    fallback = ("#333333", "#cccccc") if _current_name == "dark" else ("#e0e0e6", "#444450")
    return palette.get(event_type, fallback)


def format_member_counts(total: int, active: int) -> str:
    """The 'N members · M active' rich-text line used by the sidebar and the
    All Events header, colored from the active theme's tokens."""
    t = current_tokens()
    return (
        f"<span style='color:{t['text2']}'>{total} members</span>"
        f"&nbsp;&nbsp;<span style='color:{t['success']}'>&#9679; {active} active</span>"
    )


def apply_theme(app, theme_name: str) -> None:
    """Apply 'dark' or 'light' QSS to the entire application."""
    global _current_name
    _current_name = "dark" if theme_name == "dark" else "light"
    tokens = DARK if theme_name == "dark" else LIGHT
    app.setStyleSheet(build_qss(tokens))
    # Re-polish everything: some chrome (toolbars, property-selector styles)
    # keeps the old palette after a runtime stylesheet swap otherwise.
    style = app.style()
    for w in app.allWidgets():
        style.unpolish(w)
        style.polish(w)
        w.update()
