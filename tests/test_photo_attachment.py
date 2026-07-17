"""Access Photo attachments: header stripping for every image format (PNG
photos showed as the placeholder because only the JPEG marker was hunted)."""
import struct

from db.members import extract_attachment_image

PNG = b"\x89PNG\r\n\x1a\n" + b"png-body"
JPEG = b"\xff\xd8\xff\xe0" + b"jpeg-body"


def blob(payload: bytes, header_len: int = 20) -> bytes:
    """A synthetic attachment blob: 4-byte little-endian header length, header
    padding, then the file bytes — the layout Access uses."""
    header = struct.pack("<I", header_len) + b"\x00" * (header_len - 4)
    return header + payload


def test_png_sliced_at_declared_header_length():
    assert extract_attachment_image(blob(PNG)) == PNG


def test_jpeg_sliced_at_declared_header_length():
    assert extract_attachment_image(blob(JPEG)) == JPEG


def test_bad_offset_falls_back_to_marker_hunt():
    data = struct.pack("<I", 999999) + b"\x00" * 16 + JPEG
    assert extract_attachment_image(data) == JPEG
    data = struct.pack("<I", 999999) + b"\x00" * 16 + PNG
    assert extract_attachment_image(data) == PNG


def test_garbage_returned_unchanged():
    junk = b"\x07\x00\x00\x00 not an image at all"
    assert extract_attachment_image(junk) == junk
    assert extract_attachment_image(b"") == b""
