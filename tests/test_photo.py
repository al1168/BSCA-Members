import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def test_to_jpeg_bytes_from_png(qapp, tmp_path):
    from PyQt6.QtGui import QImage
    from gui.member_tabs import to_jpeg_bytes
    png = tmp_path / "x.png"
    img = QImage(10, 10, QImage.Format.Format_RGB32)
    img.fill(0xFF8800)
    assert img.save(str(png), "PNG")
    data = to_jpeg_bytes(str(png))
    assert len(data) > 0
    assert data[:3] == b"\xff\xd8\xff"


def test_to_jpeg_bytes_invalid_raises(qapp, tmp_path):
    from gui.member_tabs import to_jpeg_bytes
    bad = tmp_path / "x.txt"
    bad.write_text("not an image")
    with pytest.raises(ValueError):
        to_jpeg_bytes(str(bad))
