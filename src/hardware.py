"""
hardware.py — YALLA PIPS Standalone
Direct USB HID communication with the StreamDock / Stream Deck hardware.
No StreamDock software required.

Supports:
  - Elgato Stream Deck Original (15 keys)  VID 0x0fd9 PID 0x0060 / 0x006d
  - MiraBox StreamDock (15 keys)           VID 0x0fd9 (same HID protocol)
  - Custom VID/PID via config override
"""
import threading
import time
import struct
import io
import os
import sys
import logging

# ── Fix DLL search path on Windows ───────────────────────────────
if sys.platform == 'win32':
    _dll_dirs = []

    if getattr(sys, 'frozen', False):
        # Running as PyInstaller exe — DLL is in the temp extract folder
        if hasattr(sys, '_MEIPASS'):
            _dll_dirs.append(sys._MEIPASS)
        _dll_dirs.append(os.path.dirname(sys.executable))
    else:
        # Running as normal Python script
        import importlib.util
        _spec = importlib.util.find_spec('hid')
        if _spec:
            _dll_dirs.append(os.path.dirname(_spec.origin))

    for _d in _dll_dirs:
        if _d and os.path.isdir(_d):
            try:
                os.add_dll_directory(_d)
            except Exception:
                pass

import hid
from PIL import Image
Logger = logging.getLogger("yp")
# ── Known device profiles ──────────────────────────────────────────
DEVICES = [
    # MiraBox StreamDock — same HID protocol as Stream Deck
    {"name": "StreamDock",          "vid": 0x0fd9, "pid": 0x0063, "keys": 15, "img_size": 72,  "img_flip_h": True,  "img_flip_v": True,  "page_hdr": 8},
    # Elgato Stream Deck Original v2 (15 keys)
    {"name": "StreamDeck v2",       "vid": 0x0fd9, "pid": 0x006d, "keys": 15, "img_size": 72,  "img_flip_h": True,  "img_flip_v": True,  "page_hdr": 8},
    # Elgato Stream Deck Original v1 (15 keys)
    {"name": "StreamDeck v1",       "vid": 0x0fd9, "pid": 0x0060, "keys": 15, "img_size": 72,  "img_flip_h": True,  "img_flip_v": True,  "page_hdr": 16},
    # MiraBox alternate PID (seen on some units)
    {"name": "StreamDock Alt",      "vid": 0x0fd9, "pid": 0x0080, "keys": 15, "img_size": 72,  "img_flip_h": True,  "img_flip_v": True,  "page_hdr": 8},
]

PAGE_SIZE        = 512    # HID report size
IMG_REPORT_TYPE  = 0x02
HEADER_SIZE_V2   = 8

# ── Image encoding ─────────────────────────────────────────────────
import io

def _encode_image(pil_image: Image.Image, size: int, flip_h: bool, flip_v: bool) -> bytes:
    img = pil_image.resize((size, size), Image.LANCZOS).convert("RGB")
    if flip_h:
        img = img.transpose(Image.FLIP_LEFT_RIGHT)
    if flip_v:
        img = img.transpose(Image.FLIP_TOP_BOTTOM)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95)
    return buf.getvalue()


def _build_image_payload(key_index: int, img_data: bytes, page_hdr: int) -> list:
    """Split image bytes into USB HID report pages."""
    pages     = []
    remaining = img_data
    page_num  = 0
    payload_size = PAGE_SIZE - page_hdr

    while remaining:
        chunk       = remaining[:payload_size]
        remaining   = remaining[payload_size:]
        is_last     = len(remaining) == 0

        if page_hdr == 8:   # V2 / StreamDock header
            header = struct.pack("<BBBHBB",
                                 0x02,          # report ID
                                 0x07,          # image data command
                                 key_index,
                                 is_last,
                                 len(chunk) & 0xFF,
                                 (len(chunk) >> 8) & 0xFF)
            # remaining 2 bytes of 8-byte header
            header += struct.pack("<H", page_num)
        else:                # V1 header (16 bytes)
            header = struct.pack("<BBHBB",
                                 0x02,
                                 0x01,
                                 len(chunk),
                                 is_last,
                                 key_index + 1)
            header += b'\x00' * (16 - len(header))

        padded = bytearray(header) + bytearray(chunk)
        padded += bytearray(PAGE_SIZE - len(padded))
        pages.append(bytes(padded))
        page_num += 1

    return pages


# ── Device class ───────────────────────────────────────────────────
class StreamDockDevice:
    def __init__(self, profile: dict):
        self._profile  = profile
        self._hid      = hid.device()
        self._lock     = threading.Lock()
        self._running  = False
        self._cb       = None   # key press callback(key_index: int, pressed: bool)

    @property
    def key_count(self):
        return self._profile["keys"]

    @property
    def name(self):
        return self._profile["name"]

    def open(self):
        self._hid.open(self._profile["vid"], self._profile["pid"])
        self._hid.set_nonblocking(False)
        Logger.info(f"Connected to {self.name}")
        self.reset()
        self._running = True
        threading.Thread(target=self._read_loop, daemon=True).start()

    def close(self):
        self._running = False
        try:
            self._hid.close()
        except Exception:
            pass

    def set_key_callback(self, cb):
        """cb(key_index: int, pressed: bool)"""
        self._cb = cb

    def set_brightness(self, pct: int):
        """0–100"""
        pct = max(0, min(100, pct))
        payload = bytearray(PAGE_SIZE)
        if self._profile["page_hdr"] == 8:
            payload[0:6] = [0x03, 0x08, pct, 0x00, 0x00, 0x00]
        else:
            payload[0:5] = [0x05, 0x55, 0xaa, 0xd1, 0x01]
            payload[5] = pct
        with self._lock:
            self._hid.write(bytes(payload))

    def reset(self):
        payload = bytearray(PAGE_SIZE)
        if self._profile["page_hdr"] == 8:
            payload[0:2] = [0x03, 0x02]
        else:
            payload[0:5] = [0x0b, 0x63, 0x00, 0x00, 0x00]
        with self._lock:
            self._hid.write(bytes(payload))

    def set_key_image(self, key_index: int, pil_image: Image.Image):
        """Push a PIL image to a specific key (0-based index)."""
        p = self._profile
        img_data = _encode_image(pil_image, p["img_size"], p["img_flip_h"], p["img_flip_v"])
        pages    = _build_image_payload(key_index, img_data, p["page_hdr"])
        with self._lock:
            for page in pages:
                self._hid.write(page)

    def clear_key(self, key_index: int):
        blank = Image.new("RGB", (72, 72), (0, 0, 0))
        self.set_key_image(key_index, blank)

    def clear_all(self):
        for i in range(self.key_count):
            self.clear_key(i)

    def _read_loop(self):
        prev_states = [False] * self.key_count
        while self._running:
            try:
                data = self._hid.read(PAGE_SIZE, timeout_ms=200)
                if not data or len(data) < 4:
                    continue
                # V2 / StreamDock key report starts at byte 4 (after 3-byte header + count)
                for i in range(self.key_count):
                    byte_idx = 4 + i
                    if byte_idx >= len(data):
                        break
                    pressed = bool(data[byte_idx])
                    if pressed != prev_states[i]:
                        prev_states[i] = pressed
                        if self._cb:
                            try:
                                self._cb(i, pressed)
                            except Exception as e:
                                Logger.error(f"Key callback error: {e}")
            except Exception as e:
                if self._running:
                    Logger.error(f"HID read error: {e}")
                    time.sleep(0.5)


# ── Auto-detect ───────────────────────────────────────────────────
def find_device(custom_vid: int = None, custom_pid: int = None) -> StreamDockDevice | None:
    """Try all known profiles (+ optional custom) and return first found."""
    candidates = list(DEVICES)
    if custom_vid and custom_pid:
        candidates.insert(0, {
            "name": "Custom Device",
            "vid": custom_vid, "pid": custom_pid,
            "keys": 15, "img_size": 72,
            "img_flip_h": True, "img_flip_v": True, "page_hdr": 8
        })

    connected = hid.enumerate()
    connected_ids = {(d["vendor_id"], d["product_id"]) for d in connected}
    Logger.info(f"HID devices found: {connected_ids}")

    for profile in candidates:
        if (profile["vid"], profile["pid"]) in connected_ids:
            Logger.info(f"Matched: {profile['name']} ({hex(profile['vid'])}:{hex(profile['pid'])})")
            return StreamDockDevice(profile)

    Logger.error("No compatible device found. Check USB connection.")
    return None
