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

USB Selective Suspend Fix (Windows):
  Windows Update re-enables USB selective suspend which kills the write handle.
  Fix: (1) disable via registry at startup, (2) retry CreateFileW up to 8 times
  on INVALID_HANDLE_VALUE (-1), (3) validate with test write, (4) auto-reconnect
  in _win_write_block() on errors 6/995/1167/433.
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

    GENERIC_WRITE         = 0x40000000
    GENERIC_READ          = 0x80000000
    OPEN_EXISTING         = 3
    FILE_SHARE_READ       = 0x00000001
    FILE_SHARE_WRITE      = 0x00000002
    INVALID_HANDLE_VALUE  = ctypes.c_void_p(-1).value   # 0xFFFFFFFFFFFFFFFF

    # WinError codes that mean the write handle is dead
    _DEAD_HANDLE_ERRORS   = {6, 995, 1167, 433}

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


# ── USB Selective Suspend disable (Windows) ────────────────────────
def _disable_usb_selective_suspend():
    """
    Write DisableSelectiveSuspend=1 to the USB service registry key.
    Requires admin rights. Safe to call repeatedly.
    Windows Update re-enables this setting — calling it at startup prevents
    the write handle being killed after USB idle.
    """
    try:
        import winreg
        key_path = r"SYSTEM\CurrentControlSet\Services\USB"
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path,
                             0, winreg.KEY_QUERY_VALUE | winreg.KEY_SET_VALUE)
        try:
            val, _ = winreg.QueryValueEx(key, "DisableSelectiveSuspend")
            if val == 1:
                Logger.info("USB selective suspend already disabled.")
                winreg.CloseKey(key)
                return
        except FileNotFoundError:
            pass
        winreg.SetValueEx(key, "DisableSelectiveSuspend", 0, winreg.REG_DWORD, 1)
        winreg.CloseKey(key)
        Logger.info("USB selective suspend DISABLED via registry.")
    except PermissionError:
        Logger.warning("Cannot disable USB selective suspend — run as Administrator for best stability.")
    except Exception as e:
        Logger.warning(f"USB suspend registry tweak skipped: {e}")


# ── Windows raw write ─────────────────────────────────────────────
def _win_write_block(handle, data_1024: bytes):
    """Returns (success: bool, win32_error: int)."""
    payload = bytes([0x00]) + data_1024
    buf     = (ctypes.c_ubyte * REPORT_SIZE)(*payload)
    written = ctypes.c_ulong(0)
    k32     = ctypes.windll.kernel32
    ok      = k32.WriteFile(handle, buf, REPORT_SIZE, ctypes.byref(written), None)
    err     = k32.GetLastError() if not ok else 0
    return (bool(ok) and written.value == REPORT_SIZE), err


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
        # Disable USB selective suspend first — Windows Update re-enables it
        _disable_usb_selective_suspend()

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
        self._open_write_handle(retries=8, delay=0.6)

    def _open_write_handle(self, retries: int = 8, delay: float = 0.6) -> bool:
        """
        Open write handle with retry loop.
        Windows returns INVALID_HANDLE_VALUE (-1) while device is mid-resume
        from USB selective suspend — retrying with delays resolves this.
        Validates the handle with a dummy STP write before accepting.
        """
        if self._write_handle:
            ctypes.windll.kernel32.CloseHandle(self._write_handle)
            self._write_handle = None

        k32 = ctypes.windll.kernel32
        for attempt in range(retries):
            h = k32.CreateFileW(self._win_path, GENERIC_WRITE,
                                FILE_SHARE_READ | FILE_SHARE_WRITE,
                                None, OPEN_EXISTING, 0, None)
            err = k32.GetLastError()

            if h == INVALID_HANDLE_VALUE or h in (0, -1):
                Logger.warning(f"Write handle attempt {attempt+1}/{retries}: "
                               f"INVALID_HANDLE (WinError {err}) — retrying in {delay}s")
                if attempt + 1 < retries:
                    time.sleep(delay)
                continue

            # Validate with a test write
            self._write_handle = h
            if self._test_write():
                Logger.info(f"Write handle OK: {h}")
                return True
            else:
                Logger.warning(f"Write handle {h} failed test write — retrying")
                k32.CloseHandle(h)
                self._write_handle = None
                time.sleep(delay)

        # Last resort: read+write access
        h = k32.CreateFileW(self._win_path, GENERIC_READ | GENERIC_WRITE,
                            FILE_SHARE_READ | FILE_SHARE_WRITE,
                            None, OPEN_EXISTING, 0, None)
        if h not in (INVALID_HANDLE_VALUE, 0, -1):
            self._write_handle = h
            if self._test_write():
                Logger.info(f"Write handle OK (RW fallback): {h}")
                return True
            k32.CloseHandle(h)
            self._write_handle = None

        Logger.error(f"Write handle FAILED after {retries} retries.")
        return False

    def _test_write(self) -> bool:
        """Send a harmless STP no-op to confirm the handle is live."""
        if not self._write_handle:
            return False
        stp = bytearray(DATA_SIZE)
        stp[0:5]  = b'CRT\x00\x00'
        stp[5:10] = b'STP\x00\x00'
        ok, err = _win_write_block(self._write_handle, bytes(stp))
        if not ok:
            Logger.debug(f"Test write failed: WinError {err}")
        return ok

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
            # Try to reopen before giving up
            if not self._open_write_handle(retries=4, delay=0.5):
                Logger.error("WriteFile skipped: no write handle.")
                return
        ok, err = _win_write_block(self._write_handle, data)
        if ok:
            return
        Logger.error(f"WriteFile failed: {err}")
        if err in _DEAD_HANDLE_ERRORS:
            Logger.info(f"WinError {err} → reconnecting write handle...")
            if self._open_write_handle(retries=6, delay=0.6):
                # Retry once after reconnect
                ok2, err2 = _win_write_block(self._write_handle, data)
                if not ok2:
                    Logger.error(f"Retry after reconnect failed: {err2}")

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
