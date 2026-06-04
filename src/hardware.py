"""
hardware.py — YALLA PIPS
MiraBox StreamDock protocol reverse-engineered from USB capture.

Protocol (per key image update):
  1. BAT cmd  : b'CRT\x00\x00BAT\x00\x00' + jpeg_size(2B big-endian)
                + key_index(2B little-endian, 1-indexed) + zeros → 1024 bytes
  2. JPEG data: raw JPEG split into 1024-byte chunks (last chunk zero-padded)
  3. STP cmd  : b'CRT\x00\x00STP\x00\x00' + zeros → 1024 bytes

Each block sent as HID output report: [0x00] + 1024 data bytes = 1025 bytes total.
Image size: 96×96 pixels JPEG.
Key indices: 1–15 (1-indexed, row-major).
"""

import ctypes
import threading
import io
import logging
import time
import pywinusb.hid as hid_lib
from PIL import Image

Logger = logging.getLogger("yp")

# ── Windows API ────────────────────────────────────────────────────
GENERIC_WRITE    = 0x40000000
GENERIC_READ     = 0x80000000
OPEN_EXISTING    = 3
FILE_SHARE_READ  = 0x00000001
FILE_SHARE_WRITE = 0x00000002

# ── Known device profiles ─────────────────────────────────────────
DEVICES = [
    {
        "name":       "StreamDock MiraBox",
        "vid":        0x6603,
        "pid":        0x1014,
        "keys":       15,
        "img_size":   96,       # 96×96 JPEG confirmed from USB capture
        "img_flip_h": False,
        "img_flip_v": False,
        "key_offset": 1,        # keys are 1-indexed in this device
    },
    # Elgato Stream Deck (legacy fallback — Stream Deck protocol)
    {
        "name":       "StreamDeck v2",
        "vid":        0x0fd9,
        "pid":        0x006d,
        "keys":       15,
        "img_size":   72,
        "img_flip_h": True,
        "img_flip_v": True,
        "key_offset": 0,
    },
    {
        "name":       "StreamDeck v1",
        "vid":        0x0fd9,
        "pid":        0x0060,
        "keys":       15,
        "img_size":   72,
        "img_flip_h": True,
        "img_flip_v": True,
        "key_offset": 0,
    },
]

DATA_SIZE   = 1024   # bytes per HID report payload
REPORT_SIZE = 1025   # DATA_SIZE + 1 report-ID byte


# ── Image encoding ────────────────────────────────────────────────
def _encode_jpeg(pil_image: Image.Image, size: int,
                 flip_h: bool, flip_v: bool) -> bytes:
    img = pil_image.resize((size, size), Image.LANCZOS).convert("RGB")
    if flip_h:
        img = img.transpose(Image.FLIP_LEFT_RIGHT)
    if flip_v:
        img = img.transpose(Image.FLIP_TOP_BOTTOM)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


# ── Windows raw HID write ─────────────────────────────────────────
def _win_write_block(handle, data_1024: bytes) -> bool:
    """Write exactly one 1025-byte HID report (report-ID 0x00 + 1024 data)."""
    assert len(data_1024) == DATA_SIZE, f"Expected {DATA_SIZE} bytes, got {len(data_1024)}"
    payload = bytes([0x00]) + data_1024          # prepend report ID
    buf     = (ctypes.c_ubyte * REPORT_SIZE)(*payload)
    written = ctypes.c_ulong(0)
    ok = ctypes.windll.kernel32.WriteFile(
        handle, buf, REPORT_SIZE, ctypes.byref(written), None
    )
    return bool(ok) and written.value == REPORT_SIZE


# ── Device class ──────────────────────────────────────────────────
class StreamDockDevice:

    def __init__(self, profile: dict):
        self._profile      = profile
        self._device       = None          # pywinusb handle (read)
        self._write_handle = None          # ctypes handle (write)
        self._device_path  = None
        self._lock         = threading.Lock()
        self._running      = False
        self._cb           = None
        self._prev         = [False] * profile["keys"]

    # ── Properties ────────────────────────────────────────────────
    @property
    def key_count(self) -> int:
        return self._profile["keys"]

    @property
    def name(self) -> str:
        return self._profile["name"]

    # ── Lifecycle ─────────────────────────────────────────────────
    def open(self):
        f       = hid_lib.HidDeviceFilter(vendor_id=self._profile["vid"],
                                           product_id=self._profile["pid"])
        devices = f.get_devices()
        if not devices:
            raise RuntimeError(f"Device not found: {self._profile['name']}")

        self._device      = devices[0]
        self._device_path = self._device.device_path
        Logger.info(f"Device path: {self._device_path}")

        # Open for reading (key-press events via pywinusb)
        self._device.open()
        self._device.set_raw_data_handler(self._on_data)
        Logger.info(f"Connected: {self.name}")

        # Open persistent write handle via Windows API
        k32 = ctypes.windll.kernel32
        h   = k32.CreateFileW(
            self._device_path,
            GENERIC_WRITE,
            FILE_SHARE_READ | FILE_SHARE_WRITE,
            None, OPEN_EXISTING, 0, None
        )
        if h in (-1, 0):
            h = k32.CreateFileW(
                self._device_path,
                GENERIC_READ | GENERIC_WRITE,
                FILE_SHARE_READ | FILE_SHARE_WRITE,
                None, OPEN_EXISTING, 0, None
            )
        if h in (-1, 0):
            Logger.error(f"Failed to open write handle: {k32.GetLastError()}")
        else:
            self._write_handle = h
            Logger.info(f"Write handle OK: {h}")

        self._running = True

    def close(self):
        self._running = False
        if self._write_handle:
            ctypes.windll.kernel32.CloseHandle(self._write_handle)
            self._write_handle = None
        if self._device:
            try:
                self._device.close()
            except Exception:
                pass

    def set_key_callback(self, cb):
        self._cb = cb

    # ── Key-press reader ──────────────────────────────────────────
    def _on_data(self, data):
        for i in range(self._profile["keys"]):
            idx = 4 + i
            if idx >= len(data):
                break
            pressed = bool(data[idx])
            if pressed != self._prev[i]:
                self._prev[i] = pressed
                if self._cb:
                    try:
                        self._cb(i, pressed)
                    except Exception as e:
                        Logger.error(f"Key callback error: {e}")

    # ── MiraBox image protocol ────────────────────────────────────
    def set_key_image(self, key_index: int, pil_image: Image.Image):
        """
        Send a 96×96 JPEG image to a specific key.
        key_index is 0-based externally; converted to 1-based internally.
        """
        if not self._write_handle:
            return

        p        = self._profile
        jpeg     = _encode_jpeg(pil_image, p["img_size"],
                                 p["img_flip_h"], p["img_flip_v"])
        dev_key  = key_index + p["key_offset"]   # 0→1 for MiraBox

        # Pad JPEG to a multiple of DATA_SIZE
        padded_jpeg = jpeg + b'\x00' * (-len(jpeg) % DATA_SIZE)
        jpeg_size   = len(jpeg)          # real size (before padding)

        with self._lock:
            # 1 ── BAT command
            bat = bytearray(DATA_SIZE)
            bat[0:5]   = b'CRT\x00\x00'
            bat[5:10]  = b'BAT\x00\x00'
            bat[10:12] = jpeg_size.to_bytes(2, 'big')        # big-endian size
            bat[12:14] = dev_key.to_bytes(2, 'little')       # key index LE
            self._write_block(bytes(bat))

            # 2 ── JPEG data chunks
            for offset in range(0, len(padded_jpeg), DATA_SIZE):
                chunk = padded_jpeg[offset:offset + DATA_SIZE]
                self._write_block(bytes(chunk))
                time.sleep(0.001)   # 1 ms gap — device needs breathing room

            # 3 ── STP command
            stp = bytearray(DATA_SIZE)
            stp[0:5]  = b'CRT\x00\x00'
            stp[5:10] = b'STP\x00\x00'
            self._write_block(bytes(stp))

    def _write_block(self, data_1024: bytes):
        if not self._write_handle:
            return
        ok = _win_write_block(self._write_handle, data_1024)
        if not ok:
            err = ctypes.windll.kernel32.GetLastError()
            Logger.error(f"Write failed: WinError {err}")
            if err in (6, 1167):   # invalid handle / device disconnected
                self._reopen_write_handle()

    def _reopen_write_handle(self):
        if self._write_handle:
            ctypes.windll.kernel32.CloseHandle(self._write_handle)
            self._write_handle = None
        time.sleep(0.5)
        k32 = ctypes.windll.kernel32
        h   = k32.CreateFileW(
            self._device_path,
            GENERIC_WRITE,
            FILE_SHARE_READ | FILE_SHARE_WRITE,
            None, OPEN_EXISTING, 0, None
        )
        if h not in (-1, 0):
            self._write_handle = h
            Logger.info(f"Write handle reopened: {h}")

    def set_brightness(self, pct: int):
        """Brightness control — MiraBox may not support this, skip silently."""
        pass   # No brightness command found in capture; skip

    def clear_key(self, key_index: int):
        self.set_key_image(key_index, Image.new("RGB", (96, 96), (0, 0, 0)))

    def clear_all(self):
        for i in range(self.key_count):
            self.clear_key(i)


# ── Device discovery ──────────────────────────────────────────────
def find_device(custom_vid: int = None, custom_pid: int = None) -> "StreamDockDevice | None":
    candidates = list(DEVICES)
    if custom_vid and custom_pid:
        candidates.insert(0, {
            "name":       "Custom Device",
            "vid":        custom_vid,
            "pid":        custom_pid,
            "keys":       15,
            "img_size":   96,
            "img_flip_h": False,
            "img_flip_v": False,
            "key_offset": 1,
        })
    for profile in candidates:
        f = hid_lib.HidDeviceFilter(vendor_id=profile["vid"],
                                     product_id=profile["pid"])
        if f.get_devices():
            Logger.info(f"Found: {profile['name']}")
            return StreamDockDevice(profile)
    Logger.error("No compatible device found.")
    return None
