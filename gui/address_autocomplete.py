"""Google Places address autocomplete widget (native Qt, async via QtNetwork).

`parse_place_location` is pure and unit-tested. The widget (added below) degrades
to a plain text field when no API key is configured.
"""

import json
import uuid
from urllib.parse import urlencode

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLineEdit, QListWidget, QLabel
from PyQt6.QtCore import Qt, QTimer, QUrl, QPoint, pyqtSignal
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest

AUTOCOMPLETE_URL = "https://maps.googleapis.com/maps/api/place/autocomplete/json"
DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"


def parse_place_location(details_json) -> str:
    """Extract 'lng,lat' from a Place Details response, or '' if absent.

    Reads result.geometry.location.{lng,lat}. Never raises.
    """
    try:
        loc = details_json["result"]["geometry"]["location"]
        return f"{loc['lng']},{loc['lat']}"
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

    def __init__(self, api_key: str = "", parent=None):
        super().__init__(parent)
        self._api_key = api_key or ""
        self._long_lat = ""
        self._session = uuid.uuid4().hex
        self._predictions = []  # list of (description, place_id)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self._edit = QLineEdit()
        self._edit.textChanged.connect(self.textChanged)  # proxy for dirty tracking
        layout.addWidget(self._edit)

        self._status = QLabel("")
        self._status.setStyleSheet("color:#3d9e6e; font-size:10px;")
        self._status.hide()
        layout.addWidget(self._status)

        if self._api_key:
            self._popup = QListWidget()
            self._popup.setWindowFlags(Qt.WindowType.Popup)
            self._popup.itemClicked.connect(self._on_pick)
            self._nam = QNetworkAccessManager(self)
            self._timer = QTimer(self)
            self._timer.setSingleShot(True)
            self._timer.setInterval(300)
            self._timer.timeout.connect(self._request_predictions)
            self._edit.textEdited.connect(self._on_typed)
        else:
            self._popup = None

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
        self._status.hide()
        self._timer.start()

    def _request_predictions(self):
        text = self._edit.text().strip()
        if len(text) < 3:
            self._popup.hide()
            return
        params = urlencode({
            "input": text, "key": self._api_key, "sessiontoken": self._session,
            "components": "country:us", "types": "address",
        })
        reply = self._nam.get(QNetworkRequest(QUrl(f"{AUTOCOMPLETE_URL}?{params}")))
        reply.finished.connect(lambda r=reply: self._on_predictions(r))

    def _on_predictions(self, reply):
        try:
            data = json.loads(bytes(reply.readAll()).decode("utf-8"))
        except Exception:
            data = {}
        finally:
            reply.deleteLater()
        self._predictions = [
            (p.get("description", ""), p.get("place_id", ""))
            for p in data.get("predictions", [])
        ][:5]
        if not self._predictions:
            self._popup.hide()
            return
        self._popup.clear()
        for desc, _pid in self._predictions:
            self._popup.addItem(desc)
        pos = self._edit.mapToGlobal(QPoint(0, self._edit.height()))
        self._popup.move(pos)
        self._popup.setFixedWidth(self._edit.width())
        self._popup.show()

    def _on_pick(self, _item):
        idx = self._popup.currentRow()
        if idx < 0 or idx >= len(self._predictions):
            return
        desc, place_id = self._predictions[idx]
        self._popup.hide()
        self._edit.setText(desc)   # programmatic -> no _on_typed, so it won't clear long_lat
        self._request_details(place_id)

    def _request_details(self, place_id: str):
        params = urlencode({
            "place_id": place_id, "key": self._api_key,
            "sessiontoken": self._session, "fields": "geometry/location",
        })
        reply = self._nam.get(QNetworkRequest(QUrl(f"{DETAILS_URL}?{params}")))
        reply.finished.connect(lambda r=reply: self._on_details(r))

    def _on_details(self, reply):
        try:
            data = json.loads(bytes(reply.readAll()).decode("utf-8"))
        except Exception:
            data = {}
        finally:
            reply.deleteLater()
        self._long_lat = parse_place_location(data)
        if self._long_lat:
            self._status.setText("\U0001F4CD coordinates captured")
            self._status.show()
        self._session = uuid.uuid4().hex  # rotate token after a completed session
