"""Google Places address autocomplete widget (native Qt, async via QtNetwork).

`parse_place_location` is pure and unit-tested. The widget (added below) degrades
to a plain text field when no API key is configured.
"""

import json
import uuid

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLineEdit, QLabel, QCompleter
from PyQt6.QtCore import Qt, QTimer, QUrl, QByteArray, QStringListModel, pyqtSignal
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply

# Places API (New). Autocomplete is a POST; Place Details is a GET with a
# field mask. Both authenticate via the X-Goog-Api-Key header.
AUTOCOMPLETE_URL = "https://places.googleapis.com/v1/places:autocomplete"
DETAILS_URL = "https://places.googleapis.com/v1/places"  # + /{place_id}


def _pencil_icon():
    """A small pencil glyph as a QIcon for the inline 'edit' affordance."""
    from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor
    pm = QPixmap(16, 16)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setPen(QColor("#9aa0ad"))
    p.drawText(pm.rect(), Qt.AlignmentFlag.AlignCenter, "✎")
    p.end()
    return QIcon(pm)


def parse_place_location(details_json) -> str:
    """Extract 'lng,lat' from a Places API (New) Place Details response, or ''.

    Reads location.{longitude,latitude}. Never raises.
    """
    try:
        loc = details_json["location"]
        return f"{loc['longitude']},{loc['latitude']}"
    except (KeyError, TypeError):
        return ""


class AddressAutocomplete(QWidget):
    """Address field with Google Places autocomplete (async via QtNetwork).

    Drop-in-ish for a QLineEdit: text()/setText()/setPlaceholderText() and a
    textChanged(str) signal. When an API key is set, typing shows a suggestion
    popup; picking one fills the formatted address and captures long_lat
    ('lng,lat'). With no key, it is a plain line edit (graceful degradation).
    """
    textChanged = pyqtSignal(str)

    def __init__(self, api_key: str = "", view_edit: bool = False, parent=None):
        super().__init__(parent)
        self._api_key = api_key or ""
        self._long_lat = ""
        self._expecting_details = False
        self._session = uuid.uuid4().hex
        self._pred_by_desc = {}  # description -> place_id for the current suggestions
        self._view_edit = view_edit

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self._edit = QLineEdit()
        # Keep the line edit at its natural height even when this wrapper is
        # starved of vertical space (high-DPI / short windows): without this the
        # status label below would compress the line edit and clip the address
        # text. With a hard minimum, the status label yields instead.
        self._edit.setMinimumHeight(self._edit.sizeHint().height())
        self._edit.textChanged.connect(self.textChanged)  # proxy for dirty tracking
        layout.addWidget(self._edit)

        # view_edit (member Info tab): flat, selectable text by default; a pencil
        # on hover turns it editable. Default (Add Member wizard) stays editable.
        self._pencil = None
        if view_edit:
            self._edit.setObjectName("info_field")
            self._edit.setReadOnly(True)
            self._edit.setCursorPosition(0)
            self._pencil = self._edit.addAction(
                _pencil_icon(), QLineEdit.ActionPosition.TrailingPosition)
            self._pencil.setToolTip("Edit")
            self._pencil.triggered.connect(self._begin_edit)
            self._pencil.setVisible(False)
            self._edit.editingFinished.connect(self._finish_edit)

        self._status = QLabel("")
        self._status.setStyleSheet("color:#3d9e6e; font-size:10px;")
        self._status.hide()
        layout.addWidget(self._status)

        if self._api_key:
            self._nam = QNetworkAccessManager(self)
            self._timer = QTimer(self)
            self._timer.setSingleShot(True)
            self._timer.setInterval(300)
            self._timer.timeout.connect(self._request_predictions)

            # A QCompleter anchors its popup under the line edit and keeps focus
            # in the editor (so typing continues). We feed it suggestions from
            # the Places API and show them with UnfilteredPopupCompletion.
            self._model = QStringListModel(self)
            self._completer = QCompleter(self._model, self)
            self._completer.setCompletionMode(
                QCompleter.CompletionMode.UnfilteredPopupCompletion)
            self._completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            self._completer.activated[str].connect(self._on_pick)
            self._edit.setCompleter(self._completer)
            self._edit.textEdited.connect(self._on_typed)
        else:
            self._completer = None

    # ── view_edit (inline view→edit) ──────────────────────────────────────
    def _begin_edit(self):
        if not self._view_edit or not self._edit.isReadOnly():
            return
        self._edit.setReadOnly(False)
        self._edit.setProperty("editing", True)
        self._edit.style().unpolish(self._edit)
        self._edit.style().polish(self._edit)
        if self._pencil is not None:
            self._pencil.setVisible(False)
        self._edit.setFocus(Qt.FocusReason.MouseFocusReason)
        self._edit.selectAll()

    def _finish_edit(self):
        if not self._view_edit or self._edit.isReadOnly():
            return
        self._edit.setReadOnly(True)
        self._edit.setProperty("editing", False)
        self._edit.style().unpolish(self._edit)
        self._edit.style().polish(self._edit)

    def enterEvent(self, e):
        if self._pencil is not None and self._edit.isReadOnly():
            self._pencil.setVisible(True)
        super().enterEvent(e)

    def leaveEvent(self, e):
        if self._pencil is not None and self._edit.isReadOnly():
            self._pencil.setVisible(False)
        super().leaveEvent(e)

    # ── QLineEdit-ish API ─────────────────────────────────────────────────
    def text(self) -> str:
        return self._edit.text()

    def address(self) -> str:
        return self._edit.text()

    def setText(self, text: str) -> None:
        self._edit.setText(text)

    def set_address(self, text: str) -> None:
        self._edit.setText(text)

    def setPlaceholderText(self, text: str) -> None:
        self._edit.setPlaceholderText(text)

    def long_lat(self) -> str:
        return self._long_lat

    # ── typing → debounced autocomplete ───────────────────────────────────
    def _on_typed(self, _text: str):
        self._long_lat = ""        # editing invalidates a prior pick
        self._expecting_details = False
        self._status.hide()
        self._model.setStringList([])   # drop stale suggestions while we fetch
        self._timer.start()

    def _request_predictions(self):
        text = self._edit.text().strip()
        if len(text) < 3:
            return
        body = QByteArray(json.dumps({
            "input": text,
            "includedRegionCodes": ["us"],
            "sessionToken": self._session,
        }).encode("utf-8"))
        req = QNetworkRequest(QUrl(AUTOCOMPLETE_URL))
        req.setHeader(QNetworkRequest.KnownHeaders.ContentTypeHeader, "application/json")
        req.setRawHeader(b"X-Goog-Api-Key", self._api_key.encode("utf-8"))
        reply = self._nam.post(req, body)
        reply.finished.connect(lambda r=reply: self._on_predictions(r))

    def _on_predictions(self, reply):
        net_ok = reply.error() == QNetworkReply.NetworkError.NoError
        net_err = reply.errorString()
        try:
            data = json.loads(bytes(reply.readAll()).decode("utf-8"))
        except Exception:
            data = {}
        finally:
            reply.deleteLater()
        preds = []
        for s in data.get("suggestions", []):
            pp = s.get("placePrediction") or {}
            desc = (pp.get("text") or {}).get("text", "")
            pid = pp.get("placeId", "")
            if desc and pid:
                preds.append((desc, pid))
        preds = preds[:5]
        self._pred_by_desc = {desc: pid for desc, pid in preds}
        descriptions = [desc for desc, _pid in preds]
        self._model.setStringList(descriptions)
        if descriptions:
            self._completer.complete()        # show the popup under the line edit
            self._status.hide()
            return
        self._completer.popup().hide()
        # Surface why nothing came back (e.g. PERMISSION_DENIED) instead of
        # failing silently — otherwise a bad key looks like a broken feature.
        err = data.get("error") or {}
        if err:
            self._show_status(
                f"Address lookup: {err.get('status', 'error')}"
                + (f" — {err.get('message')}" if err.get("message") else ""),
                error=True)
        elif not net_ok:
            self._show_status(f"Address lookup failed: {net_err}", error=True)

    def _show_status(self, text: str, *, error: bool = False) -> None:
        color = "#d05555" if error else "#3d9e6e"
        self._status.setStyleSheet(f"color:{color}; font-size:10px;")
        self._status.setText(text)
        self._status.show()

    def _on_pick(self, description: str):
        # The completer has already filled the line edit with `description`
        # (programmatic -> no _on_typed, no lookup). Fetch its coordinates.
        place_id = self._pred_by_desc.get(description, "")
        if not place_id:
            return
        self._expecting_details = True
        self._request_details(place_id)

    def _request_details(self, place_id: str):
        req = QNetworkRequest(QUrl(f"{DETAILS_URL}/{place_id}?sessionToken={self._session}"))
        req.setRawHeader(b"X-Goog-Api-Key", self._api_key.encode("utf-8"))
        req.setRawHeader(b"X-Goog-FieldMask", b"location")
        reply = self._nam.get(req)
        reply.finished.connect(lambda r=reply: self._on_details(r))

    def _on_details(self, reply):
        try:
            if not self._expecting_details:
                return  # user edited after picking; ignore the stale reply
            self._expecting_details = False
            try:
                data = json.loads(bytes(reply.readAll()).decode("utf-8"))
            except Exception:
                data = {}
            self._long_lat = parse_place_location(data)
            if self._long_lat:
                self._show_status("\U0001F4CD coordinates captured")
            self._session = uuid.uuid4().hex  # rotate token after a completed session
        finally:
            reply.deleteLater()
