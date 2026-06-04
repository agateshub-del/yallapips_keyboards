"""
hardware.py — YALLA PIPS
MiraBox StreamDock — protocol from USB capture.
Key layout: device numbers columns right-to-left.
"""
import ctypes, threading, io, logging, time
import pywinusb.hid as hid_lib
from PIL import Image

Logger = logging.getLogger("yp")

GENERIC_WRITE    = 0x40000000
GENERIC_READ     = 0x80000000
OPEN_EXISTING    = 3
FILE_SHARE_READ  = 0x00000001
FILE_SHARE_WRITE = 0x00000002

# ── Key remapping ─────────────────────────────────────────────────
# Device numbers keys column-by-column, RIGHT to LEFT.
# Our logical order is column-by-column, LEFT to RIGHT.
# Logical index 0-14 → Device key 1-15 (1-indexed)
KEY_REMAP = [13, 14, 15,   # col0 (Execute):  BUY/SELL/CLOSE ALL   → device col5
              10, 11, 12,   # col1 (CloseTrade):LOSING/PROFIT/SL_BE  → device col4
               7,  8,  9,  # col2 (Partial):   25/50/75%             → device col3
               4,  5,  6,  # col3 (StopLoss):  AUTO_BE/PARTIAL/TRAIL → device col2
               1,  2,  3]  # col4 (Platform):  TV/FF/MT5             → device col1

# Reverse: device key 0-indexed → logical index 0-14
KEY_REVERSE = {v - 1: k for k, v in enumerate(KEY_REMAP)}

DEVICES = [
    {"name": "StreamDock MiraBox", "vid": 0x6603, "pid": 0x1014,
     "keys": 15, "img_size": 96, "img_flip_h": False, "img_flip_v": False},
    {"name": "StreamDeck v2",      "vid": 0x0fd9, "pid": 0x006d,
     "keys": 15, "img_size": 72, "img_flip_h": True,  "img_flip_v": True},
    {"name": "StreamDeck v1",      "vid": 0x0fd9, "pid": 0x0060,
     "keys": 15, "img_size": 72, "img_flip_h": True,  "img_flip_v": True},
]

DATA_SIZE   = 1024
REPORT_SIZE = 1025


def _encode_jpeg(img: Image.Image, size: int, fh: bool, fv: bool) -> bytes:
    img = img.resize((size, size), Image.LANCZOS).convert("RGB")
    if fh: img = img.transpose(Image.FLIP_LEFT_RIGHT)
    if fv: img = img.transpose(Image.FLIP_TOP_BOTTOM)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


def _win_write_block(handle, data_1024: bytes) -> bool:
    payload = bytes([0x00]) + data_1024
    buf     = (ctypes.c_ubyte * REPORT_SIZE)(*payload)
    written = ctypes.c_ulong(0)
    ok = ctypes.windll.kernel32.WriteFile(
        handle, buf, REPORT_SIZE, ctypes.byref(written), None)
    return bool(ok) and written.value == REPORT_SIZE


class StreamDockDevice:

    def __init__(self, profile):
        self._profile      = profile
        self._device       = None
        self._write_handle = None
        self._device_path  = None
        self._lock         = threading.Lock()
        self._running      = False
        self._cb           = None
        self._prev         = [False] * profile["keys"]

    @property
    def key_count(self): return self._profile["keys"]

    @property
    def name(self): return self._profile["name"]

    def open(self):
        f       = hid_lib.HidDeviceFilter(vendor_id=self._profile["vid"],
                                           product_id=self._profile["pid"])
        devices = f.get_devices()
        if not devices:
            raise RuntimeError(f"Device not found: {self._profile['name']}")
        self._device      = devices[0]
        self._device_path = self._device.device_path
        self._device.open()
        self._device.set_raw_data_handler(self._on_data)
        Logger.info(f"Connected: {self.name}")
        self._open_write_handle()
        self._running = True

    def _open_write_handle(self):
        k32 = ctypes.windll.kernel32
        h   = k32.CreateFileW(self._device_path, GENERIC_WRITE,
                               FILE_SHARE_READ | FILE_SHARE_WRITE,
                               None, OPEN_EXISTING, 0, None)
        if h in (-1, 0):
            h = k32.CreateFileW(self._device_path,
                                 GENERIC_READ | GENERIC_WRITE,
                                 FILE_SHARE_READ | FILE_SHARE_WRITE,
                                 None, OPEN_EXISTING, 0, None)
        if h not in (-1, 0):
            self._write_handle = h
            Logger.info(f"Write handle OK: {h}")
        else:
            Logger.error(f"Write handle FAILED: {k32.GetLastError()}")

    def close(self):
        self._running = False
        if self._write_handle:
            ctypes.windll.kernel32.CloseHandle(self._write_handle)
            self._write_handle = None
        if self._device:
            try: self._device.close()
            except Exception: pass

    def set_key_callback(self, cb):
        self._cb = cb

    def _on_data(self, data):
        """Translate raw device key index → logical index → callback."""
        for raw_i in range(self._profile["keys"]):
            idx = 4 + raw_i
            if idx >= len(data): break
            pressed = bool(data[idx])
            if pressed != self._prev[raw_i]:
                self._prev[raw_i] = pressed
                if self._cb:
                    # Remap raw device key → logical action index
                    logical = KEY_REVERSE.get(raw_i, raw_i)
                    try:
                        self._cb(logical, pressed)
                    except Exception as e:
                        Logger.error(f"Callback error: {e}")

    def set_key_image(self, logical_index: int, pil_image: Image.Image):
        """Send image to the physically correct key using KEY_REMAP."""
        if not self._write_handle:
            return
        p        = self._profile
        jpeg     = _encode_jpeg(pil_image, p["img_size"],
                                 p["img_flip_h"], p["img_flip_v"])
        dev_key  = KEY_REMAP[logical_index]     # logical → device key (1-indexed)

        padded   = jpeg + b'\x00' * (-len(jpeg) % DATA_SIZE)
        with self._lock:
            # 1. BAT command
            bat = bytearray(DATA_SIZE)
            bat[0:5]   = b'CRT\x00\x00'
            bat[5:10]  = b'BAT\x00\x00'
            bat[10:12] = len(jpeg).to_bytes(2, 'big')
            bat[12:14] = dev_key.to_bytes(2, 'little')
            self._write_block(bytes(bat))
            # 2. JPEG chunks
            for off in range(0, len(padded), DATA_SIZE):
                self._write_block(padded[off:off + DATA_SIZE])
                time.sleep(0.001)
            # 3. STP command
            stp = bytearray(DATA_SIZE)
            stp[0:5]  = b'CRT\x00\x00'
            stp[5:10] = b'STP\x00\x00'
            self._write_block(bytes(stp))

    def _write_block(self, data: bytes):
        if not self._write_handle: return
        ok = _win_write_block(self._write_handle, data)
        if not ok:
            err = ctypes.windll.kernel32.GetLastError()
            Logger.error(f"WriteFile failed: {err}")
            if err in (6, 1167):
                time.sleep(0.5)
                self._open_write_handle()

    def set_brightness(self, pct): pass   # not supported on MiraBox

    def clear_key(self, i):
        self.set_key_image(i, Image.new("RGB", (96, 96), (0, 0, 0)))

    def clear_all(self):
        for i in range(self.key_count): self.clear_key(i)


def find_device(custom_vid=None, custom_pid=None):
    candidates = list(DEVICES)
    if custom_vid and custom_pid:
        candidates.insert(0, {"name": "Custom Device",
                               "vid": custom_vid, "pid": custom_pid,
                               "keys": 15, "img_size": 96,
                               "img_flip_h": False, "img_flip_v": False})
    for p in candidates:
        f = hid_lib.HidDeviceFilter(vendor_id=p["vid"], product_id=p["pid"])
        if f.get_devices():
            Logger.info(f"Found: {p['name']}")
            return StreamDockDevice(p)
    Logger.error("No compatible device found.")
    return None
