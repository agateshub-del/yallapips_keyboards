"""
hardware.py — YALLA PIPS  (Cross-platform: Windows + macOS)

Windows : pywinusb for read  +  ctypes WriteFile for write
macOS   : hidapi (cython-hidapi) for both read and write

MiraBox StreamDock protocol (from USB capture):
  BAT cmd  : CRT\\x00\\x00 BAT\\x00\\x00 + jpeg_size(2B BE) + key_idx(2B LE) + zeros
  JPEG data: raw JPEG split into 1024-byte chunks
  STP cmd  : CRT\\x00\\x00 STP\\x00\\x00 + zeros
  Report   : [0x00] + 1024 data bytes = 1025 bytes total
  Key input: data[10]=key_number(1-15), data[11]=pressed(1/0)
"""
import sys
import threading
import io
import logging
import time

from PIL import Image

Logger       = logging.getLogger("yp")
PLATFORM     = sys.platform          # 'win32' | 'darwin' | 'linux'
IS_WINDOWS   = PLATFORM == "win32"
IS_MAC       = PLATFORM == "darwin"

KEY_REMAP   = [13, 14, 15, 10, 11, 12, 7, 8, 9, 4, 5, 6, 1, 2, 3]
KEY_REVERSE = {v - 1: k for k, v in enumerate(KEY_REMAP)}

DEVICES = [
    {"name": "StreamDock MiraBox", "vid": 0x6603, "pid": 0x1014,
     "keys": 15, "img_size": 96, "img_flip_h": False, "img_flip_v": False, "rotate": 90},
    {"name": "StreamDeck v2",      "vid": 0x0fd9, "pid": 0x006d,
     "keys": 15, "img_size": 72, "img_flip_h": True,  "img_flip_v": True,  "rotate": 0},
    {"name": "StreamDeck v1",      "vid": 0x0fd9, "pid": 0x0060,
     "keys": 15, "img_size": 72, "img_flip_h": True,  "img_flip_v": True,  "rotate": 0},
]

DATA_SIZE   = 1024
REPORT_SIZE = 1025   # report-ID byte + 1024 data


# ── Platform imports ──────────────────────────────────────────────
if IS_WINDOWS:
    import ctypes
    import pywinusb.hid as hid_lib

    GENERIC_WRITE    = 0x40000000
    GENERIC_READ     = 0x80000000
    OPEN_EXISTING    = 3
    FILE_SHARE_READ  = 0x00000001
    FILE_SHARE_WRITE = 0x00000002

else:   # macOS / Linux
    try:
        import hid as hidapi
        _HIDAPI_OK = True
    except ImportError:
        Logger.error("hidapi not installed. Run: pip install hidapi")
        _HIDAPI_OK = False


# ── Image encoding ────────────────────────────────────────────────
def _encode_jpeg(img, size, fh, fv, rotate=0):
    img = img.resize((size, size), Image.LANCZOS).convert("RGB")
    if fh:
        img = img.transpose(Image.FLIP_LEFT_RIGHT)
    if fv:
        img = img.transpose(Image.FLIP_TOP_BOTTOM)
    if rotate:
        img = img.rotate(rotate)          # positive = CCW in PIL
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


# ── Windows raw write ─────────────────────────────────────────────
def _win_write_block(handle, data_1024: bytes) -> bool:
    payload = bytes([0x00]) + data_1024
    buf     = (ctypes.c_ubyte * REPORT_SIZE)(*payload)
    written = ctypes.c_ulong(0)
    ok = ctypes.windll.kernel32.WriteFile(
        handle, buf, REPORT_SIZE, ctypes.byref(written), None)
    return bool(ok) and written.value == REPORT_SIZE


# ══════════════════════════════════════════════════════════════════
class StreamDockDevice:

    def __init__(self, profile):
        self._profile      = profile
        self._lock         = threading.Lock()
        self._running      = False
        self._cb           = None
        self._prev         = [False] * profile["keys"]

        # Windows handles
        self._win_device   = None
        self._win_path     = None
        self._write_handle = None

        # macOS handle
        self._mac_device   = None
        self._mac_thread   = None

    @property
    def key_count(self): return self._profile["keys"]

    @property
    def name(self):      return self._profile["name"]

    # ── Open ──────────────────────────────────────────────────────
    def open(self):
        if IS_WINDOWS:
            self._open_windows()
        else:
            self._open_mac()
        self._running = True

    # ── Windows open ──────────────────────────────────────────────
    def _open_windows(self):
        f = hid_lib.HidDeviceFilter(vendor_id=self._profile["vid"],
                                     product_id=self._profile["pid"])
        devices = f.get_devices()
        if not devices:
            raise RuntimeError(f"Device not found: {self._profile['name']}")
        self._win_device = devices[0]
        self._win_path   = self._win_device.device_path
        self._win_device.open()
        self._win_device.set_raw_data_handler(self._on_data)
        Logger.info(f"Connected (Windows): {self.name}")
        self._open_write_handle()

    def _open_write_handle(self):
        k32 = ctypes.windll.kernel32
        h   = k32.CreateFileW(self._win_path, GENERIC_WRITE,
                               FILE_SHARE_READ | FILE_SHARE_WRITE,
                               None, OPEN_EXISTING, 0, None)
        if h in (-1, 0):
            h = k32.CreateFileW(self._win_path,
                                 GENERIC_READ | GENERIC_WRITE,
                                 FILE_SHARE_READ | FILE_SHARE_WRITE,
                                 None, OPEN_EXISTING, 0, None)
        if h not in (-1, 0):
            self._write_handle = h
            Logger.info(f"Write handle OK: {h}")
        else:
            Logger.error(f"Write handle FAILED: {ctypes.windll.kernel32.GetLastError()}")

    # ── macOS open ────────────────────────────────────────────────
    def _open_mac(self):
        if not _HIDAPI_OK:
            raise RuntimeError("hidapi not installed. Run: pip install hidapi")
        self._mac_device = hidapi.device()
        self._mac_device.open(self._profile["vid"], self._profile["pid"])
        self._mac_device.set_nonblocking(True)
        Logger.info(f"Connected (macOS): {self.name}")
        # Start polling thread for key events
        self._mac_thread = threading.Thread(target=self._mac_read_loop, daemon=True)
        self._mac_thread.start()

    def _mac_read_loop(self):
        """Poll HID device for key press events (macOS)."""
        while self._running:
            try:
                data = self._mac_device.read(25, timeout_ms=50)
                if data:
                    self._on_data(data)
            except Exception as e:
                Logger.error(f"Mac read error: {e}")
                time.sleep(0.1)

    # ── Close ─────────────────────────────────────────────────────
    def close(self):
        self._running = False
        if IS_WINDOWS:
            if self._write_handle:
                ctypes.windll.kernel32.CloseHandle(self._write_handle)
                self._write_handle = None
            if self._win_device:
                try: self._win_device.close()
                except Exception: pass
        else:
            if self._mac_device:
                try: self._mac_device.close()
                except Exception: pass

    # ── Key callback ──────────────────────────────────────────────
    def set_key_callback(self, cb):
        self._cb = cb

    def _on_data(self, data):
        if len(data) < 12:
            return
        key_num    = data[10]
        is_pressed = bool(data[11])
        if key_num < 1 or key_num > 15:
            return
        raw_i   = key_num - 1
        logical = KEY_REVERSE.get(raw_i, raw_i)
        if is_pressed != self._prev[raw_i]:
            self._prev[raw_i] = is_pressed
            if is_pressed:
                Logger.info(f"Key pressed: device={key_num} logical={logical}")
            if self._cb:
                try:
                    self._cb(logical, is_pressed)
                except Exception as e:
                    Logger.error(f"Callback error: {e}")

    # ── Image send ────────────────────────────────────────────────
    def _send_jpeg_to_key(self, device_key_number: int, jpeg_bytes: bytes):
        padded = jpeg_bytes + b'\x00' * (-len(jpeg_bytes) % DATA_SIZE)
        with self._lock:
            bat = bytearray(DATA_SIZE)
            bat[0:5]   = b'CRT\x00\x00'
            bat[5:10]  = b'BAT\x00\x00'
            bat[10:12] = len(jpeg_bytes).to_bytes(2, 'big')
            bat[12:14] = device_key_number.to_bytes(2, 'little')
            self._write_block(bytes(bat))
            for off in range(0, len(padded), DATA_SIZE):
                self._write_block(padded[off:off + DATA_SIZE])
                time.sleep(0.001)
            stp = bytearray(DATA_SIZE)
            stp[0:5]  = b'CRT\x00\x00'
            stp[5:10] = b'STP\x00\x00'
            self._write_block(bytes(stp))

    def _write_block(self, data: bytes):
        if IS_WINDOWS:
            self._win_write_block(data)
        else:
            self._mac_write_block(data)

    def _win_write_block(self, data: bytes):
        if not self._write_handle:
            return
        ok = _win_write_block(self._write_handle, data)
        if not ok:
            err = ctypes.windll.kernel32.GetLastError()
            Logger.error(f"WriteFile failed: {err}")
            if err in (6, 1167):
                time.sleep(0.5)
                self._open_write_handle()

    def _mac_write_block(self, data: bytes):
        if not self._mac_device:
            return
        try:
            payload = [0x00] + list(data[:DATA_SIZE])
            result  = self._mac_device.write(payload)
            if result < 0:
                Logger.error(f"Mac HID write failed: {result}")
        except Exception as e:
            Logger.error(f"Mac write error: {e}")

    def set_key_image(self, logical_index: int, pil_image: Image.Image):
        p       = self._profile
        jpeg    = _encode_jpeg(pil_image, p["img_size"],
                                p["img_flip_h"], p["img_flip_v"],
                                p.get("rotate", 0))
        dev_key = KEY_REMAP[logical_index]
        self._send_jpeg_to_key(dev_key, jpeg)

    def set_long_display_panel(self, key_num: int, pil_image: Image.Image):
        """
        Send a 96x96 image to one panel of the long strip display.
        key_num: 16 = top, 17 = middle, 18 = bottom
        """
        p    = self._profile
        jpeg = _encode_jpeg(pil_image, p["img_size"],
                             p["img_flip_h"], p["img_flip_v"],
                             p.get("rotate", 0))
        self._send_jpeg_to_key(key_num, jpeg)

    def set_long_display(self, pil_image: Image.Image):
        """Send single image to bottom panel (key 18) — legacy."""
        self.set_long_display_panel(18, pil_image)


    def set_brightness(self, pct): pass  # not supported on MiraBox

    def clear_key(self, i):
        self.set_key_image(i, Image.new("RGB", (96, 96), (0, 0, 0)))

    def clear_all(self):
        for i in range(self.key_count):
            self.clear_key(i)


# ── Device discovery ──────────────────────────────────────────────
def find_device(custom_vid=None, custom_pid=None):
    candidates = list(DEVICES)
    if custom_vid and custom_pid:
        candidates.insert(0, {
            "name": "Custom Device", "vid": custom_vid, "pid": custom_pid,
            "keys": 15, "img_size": 96,
            "img_flip_h": False, "img_flip_v": False, "rotate": 90
        })

    if IS_WINDOWS:
        for p in candidates:
            f = hid_lib.HidDeviceFilter(vendor_id=p["vid"], product_id=p["pid"])
            if f.get_devices():
                Logger.info(f"Found: {p['name']}")
                return StreamDockDevice(p)

    else:  # macOS / Linux
        if not _HIDAPI_OK:
            Logger.error("hidapi not installed")
            return None
        for p in candidates:
            devs = hidapi.enumerate(p["vid"], p["pid"])
            if devs:
                Logger.info(f"Found: {p['name']} (macOS)")
                return StreamDockDevice(p)

    Logger.error("No compatible device found.")
    return None
